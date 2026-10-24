"""Runs the fictional test projects (tests/projects/*.json) through the whole agent with
the real models and compares the result with the expectations.

    uv run python -m eval.run_eval                       # all projects
    uv run python -m eval.run_eval sensor-prototyp       # selected projects
    uv run python -m eval.run_eval --save demo           # also save results to backend/demo/

Answers in a project file are option labels by profile field. Programs that are not in
the knowledge base yet are reported as such, not as misses.
"""

import argparse
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.agent.answers import apply_answers
from app.agent.orchestrator import run_analysis
from app.agent.profile import extract_profile
from app.agent.questions import build_questions
from app.config import BACKEND_DIR, KNOWLEDGE_BASE_DIR, REPO_DIR, get_settings
from app.knowledge_base.loader import KnowledgeBase, load_knowledge_base
from app.llm.openai_client import OpenAIClient
from app.llm.usage import Usage, current_usage
from app.models.contract import Answer, ProfileRequest, QuestionSet, RunResult
from app.runs import RunStore

PROJECTS_DIR = REPO_DIR / "tests" / "projects"
BADGES = {"erfuellt": "✓", "annahme": "~", "unbekannt": "?", "nicht_erfuellt": "✗"}


@dataclass
class Report:
    project: str
    lines: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def add(self, line: str) -> None:
        self.lines.append(line)

    def problem(self, line: str) -> None:
        self.problems.append(line)


def _answers(questions: QuestionSet, wanted: dict[str, str]) -> list[Answer]:
    return [
        Answer(question_id=q.id, profile_field=q.profile_field, answer=wanted[q.profile_field])
        for q in questions.questions
        if q.profile_field in wanted
    ]


async def run_project(path: Path, kb: KnowledgeBase, llm: OpenAIClient) -> tuple[Report, Any]:
    project = json.loads(path.read_text(encoding="utf-8"))
    expected = project["expected"]
    report = Report(project["id"])
    usage = Usage()
    token = current_usage.set(usage)
    started = time.monotonic()
    try:
        response = await extract_profile(ProfileRequest.model_validate(project["input"]), llm)
        if response.status == "needs_clarification":
            report.add(f"Rückfrage statt Profil: {response.clarification.question}")
            if not expected["needs_clarification"]:
                report.problem("needs_clarification, obwohl ein Profil erwartet war")
            return _finish(report, usage, started, None), None
        if expected["needs_clarification"]:
            report.problem("Profil erstellt, obwohl needs_clarification erwartet war")
        profile = response.profile
        _compare_profile(report, profile.fields, expected["profile"])
        questions = build_questions(profile, kb)
        report.add(f"Rückfragen: {', '.join(q.id for q in questions.questions) or 'keine'}")
        profile = apply_answers(profile, _answers(questions, project["answers"]), kb)
        settings = get_settings()
        recorder = RunStore().create(profile, settings.today())
        result = await run_analysis(profile, kb, llm, recorder, settings.today())
    finally:
        current_usage.reset(token)
    usage.calls += recorder.usage.calls
    _describe(report, result, recorder.downgrades)
    _compare_programs(report, result, expected, kb)
    return _finish(report, usage, started, result), result


def _compare_profile(report: Report, fields: dict, expected: dict[str, Any]) -> None:
    for name, value in expected.items():
        actual = fields.get(name)
        got = actual.value if actual else None
        # Lists: the expected values must be there; more is fine.
        same = set(value) <= set(got) if isinstance(value, list) and got else got == value
        if not same:
            report.problem(f"Profil {name}: erwartet {value!r}, erhalten {got!r}")


def _describe(report: Report, result: RunResult, downgrades: int) -> None:
    report.add(f"Status: {result.status}, Herabstufungen durch die Evidenz-Regel: {downgrades}")
    for match in result.matches:
        counts = {s: sum(c.state == s for c in match.criteria) for s in BADGES}
        badges = " ".join(f"{BADGES[s]}{n}" for s, n in counts.items())
        rank = f"#{match.rank}" if match.rank else "-"
        status = match.fit or f"FEHLER: {match.error}"
        report.add(f"- {rank} {match.program_id}:{match.instrument_id}: {status} ({badges})")
        for gap in match.gaps:
            report.add(f"    Lücke {gap.type} {gap.criterion_ids}: {gap.hint or gap.lever}")
    for rejected in result.rejected:
        report.add(f"- abgelehnt {rejected.program_id}:{rejected.instrument_id}: {rejected.rule}")


def _compare_programs(report: Report, result: RunResult, expected: dict, kb: KnowledgeBase) -> None:
    for item in expected["programs"]:
        if kb.get(item["program_id"]) is None:
            report.add(f"(nicht in der Wissensbasis: {item['program_id']})")
            continue
        matches = [
            m
            for m in result.matches
            if m.program_id == item["program_id"]
            and item["instrument_id"] in (None, m.instrument_id)
        ]
        if not any(m.fit in item["fit"] for m in matches):
            got = [m.fit for m in matches] or ["abgelehnt"]
            line = f"{item['program_id']}: erwartet {item['fit']}, erhalten {got}"
            (report.problem if item["required"] else report.add)(line)
    for item in expected["rejected"]:
        if kb.get(item["program_id"]) is None:
            continue
        fitting = [
            m
            for m in result.matches
            if m.program_id == item["program_id"]
            and item["instrument_id"] in (None, m.instrument_id)
            and m.fit in ("passt_gut", "passt_mit_anpassung")
        ]
        if fitting:
            report.problem(f"{item['program_id']}: sollte nicht passen, ist {fitting[0].fit}")


def _finish(report: Report, usage: Usage, started: float, result: RunResult | None) -> Report:
    report.add(
        f"Dauer {time.monotonic() - started:.1f} s, {len(usage.calls)} KI-Aufrufe, "
        f"Tokens {usage.input_tokens} rein / {usage.output_tokens} raus, "
        f"Kosten ca. USD {usage.cost_usd:.4f}"
    )
    return report


async def main(names: list[str], save: Path | None) -> int:
    kb = load_knowledge_base(KNOWLEDGE_BASE_DIR)
    llm = OpenAIClient(get_settings())
    paths = sorted(PROJECTS_DIR.glob("*.json"))
    if names:
        paths = [p for p in paths if p.stem in names]
    failed = 0
    for path in paths:
        report, result = await run_project(path, kb, llm)
        print(f"\n## {report.project}")
        print("\n".join(report.lines))
        if report.problems:
            failed += 1
            print("Abweichungen:\n" + "\n".join(f"- {p}" for p in report.problems))
        if save and result is not None:
            save.mkdir(parents=True, exist_ok=True)
            out = save / f"{path.stem}.json"
            out.write_text(result.model_dump_json(indent=1) + "\n", encoding="utf-8")
    print(f"\n{len(paths) - failed} von {len(paths)} Projekten ohne Abweichung.")
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("projects", nargs="*", help="Dateinamen ohne .json")
    parser.add_argument("--save", type=Path, help="Ordner für die Ergebnisse, z. B. demo")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    save = BACKEND_DIR / args.save if args.save else None
    raise SystemExit(asyncio.run(main(args.projects, save)))
