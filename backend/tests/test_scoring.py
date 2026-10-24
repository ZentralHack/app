import json
from datetime import date
from fractions import Fraction

import pytest

from app.agent.scoring import (
    RankEntry,
    assign_ranks,
    is_competitive,
    mostly_unknown,
    muss_met_share,
    score,
)
from app.config import KNOWLEDGE_BASE_DIR, REPO_DIR
from app.knowledge_base.flat import FlatInstrument
from app.knowledge_base.loader import KnowledgeBase, load_knowledge_base
from app.models.contract import CriterionResult, SourceLink


@pytest.fixture
def lib(kb: KnowledgeBase) -> FlatInstrument:
    return next(i for i in kb.instruments() if i.program.id == "lib")


@pytest.fixture
def sensora_criteria() -> list[CriterionResult]:
    """LIB criteria of the example run (design/examples/run_result.json), with
    praesenz_raeume as before the follow-up question: unknown."""
    path = REPO_DIR / "design" / "examples" / "run_result.json"
    match = json.loads(path.read_text(encoding="utf-8"))["matches"][0]
    criteria = [CriterionResult.model_validate(c) for c in match["criteria"]]
    return _with(criteria, praesenz_raeume="unbekannt")


def _with(criteria: list[CriterionResult], **states: str) -> list[CriterionResult]:
    return [c.model_copy(update={"state": states.get(c.criterion_id, c.state)}) for c in criteria]


def test_sensora_lib_fits_with_missing_infos(lib, sensora_criteria):
    result = score(lib, sensora_criteria, exclusion_hit=False)
    # 2 of 12 applicable muss unknown is below a third → passt_gut, but never without gaps.
    assert result.fit == "passt_gut"
    assert [(g.type, g.criterion_ids) for g in result.gaps] == [
        ("infos_fehlen", ["praesenz_raeume"]),
        ("infos_fehlen", ["nachhaltigkeit"]),
        ("infos_fehlen", ["keine_ausstaende"]),
    ]
    nachhaltigkeit = result.gaps[1]
    assert nachhaltigkeit.lever == "Kompakte Nachhaltigkeitsübersicht (2-3 Seiten) erstellen"
    assert nachhaltigkeit.source.locator == "N 18"
    assert result.gaps[0].lever is None
    assert result.gaps[0].source.locator == "N 21-23"
    # 6 met and 4 assumed (counting half) of 12 applicable muss criteria.
    assert result.muss_met_share == Fraction(8, 12)


def test_every_unknown_muss_has_a_gap(lib, sensora_criteria):
    for criterion in sensora_criteria:
        if criterion.kind != "muss":
            continue
        result = score(lib, _with(sensora_criteria, **{criterion.criterion_id: "unbekannt"}), False)
        if result.fit == "passt_gut":
            gap_ids = {i for g in result.gaps if g.type == "infos_fehlen" for i in g.criterion_ids}
            assert criterion.criterion_id in gap_ids


def test_unmet_muss_without_lever_does_not_fit(lib, sensora_criteria):
    result = score(lib, _with(sensora_criteria, fei_taetigkeit="nicht_erfuellt"), False)
    assert result.fit == "passt_nicht"


def test_unmet_muss_with_lever_fits_with_adjustment(lib, sensora_criteria):
    result = score(lib, _with(sensora_criteria, revision="nicht_erfuellt"), False)
    assert result.fit == "passt_mit_anpassung"
    assert result.gaps[0].type == "anpassung"
    assert result.gaps[0].lever.startswith("Prüfbericht nach SA-CH")


def test_exclusion_hit_does_not_fit(lib, sensora_criteria):
    assert score(lib, sensora_criteria, exclusion_hit=True).fit == "passt_nicht"


def test_too_many_unknown_muss(lib, sensora_criteria):
    unknown = dict.fromkeys(["neuartig", "systematisch"], "unbekannt")
    # 4 of 12 is exactly a third: still passt_gut.
    assert score(lib, _with(sensora_criteria, **unknown), False).fit == "passt_gut"
    unknown["revision"] = "unbekannt"
    assert score(lib, _with(sensora_criteria, **unknown), False).fit == "passt_mit_anpassung"


def test_not_applicable_leaves_the_count(lib, sensora_criteria):
    unknown = dict.fromkeys(["neuartig", "systematisch"], "unbekannt")
    # 4 unknown of 11 applicable muss is more than a third.
    criteria = _with(sensora_criteria, ausfuehrung_luzern="nicht_anwendbar", **unknown)
    assert score(lib, criteria, False).fit == "passt_mit_anpassung"


def test_missing_partner_is_fixable(lib, sensora_criteria):
    source = SourceLink(title="Handbuch", url="https://example.test", locator=None)
    partner = CriterionResult(
        criterion_id="partner_forschungspartner",
        scope="filter",
        text="Ein Forschungspartner ist beteiligt.",
        kind="muss",
        state="nicht_erfuellt",
        reason="Kein Partner genannt.",
        evidence=["partner"],
        profile_fields=["partner"],
        question=None,
        source=source,
    )
    result = score(lib, [*sensora_criteria, partner], False)
    assert result.fit == "passt_mit_anpassung"
    assert result.gaps[0].lever == "Forschungspartner beiziehen"
    assert result.gaps[0].type == "anpassung"


def _entry(key, fit, share=Fraction(1), deadline=None, entitlement="kein_rechtsanspruch", **flags):
    return RankEntry(key, fit, share, deadline, entitlement, **flags)


def test_ranking_order():
    ranks = assign_ranks(
        [
            _entry("nicht", "passt_nicht"),
            _entry("anpassung", "passt_mit_anpassung"),
            _entry("gut-halb", "passt_gut", Fraction(1, 2)),
            _entry("gut-spaet", "passt_gut", deadline=date(2027, 6, 1)),
            _entry("gut-frueh", "passt_gut", deadline=date(2027, 1, 31)),
            _entry("gut-frueh-anspruch", "passt_gut", deadline=date(2027, 1, 31),
                   entitlement="rechtsanspruch_im_budget"),
        ]
    )  # fmt: skip
    assert ranks == {
        "gut-frueh-anspruch": 1,
        "gut-frueh": 2,
        "gut-spaet": 3,
        "gut-halb": 4,
        "anpassung": 5,
        "nicht": None,
    }


def test_competition_ranks_after_the_rest_of_its_level():
    ranks = assign_ranks(
        [
            _entry("wettbewerb", "passt_gut", deadline=date(2026, 11, 4), entitlement="wettbewerb",
                   competitive=True),
            _entry("normal-halb", "passt_gut", Fraction(1, 2)),
            _entry("anpassung", "passt_mit_anpassung"),
        ]
    )  # fmt: skip
    assert ranks == {"normal-halb": 1, "wettbewerb": 2, "anpassung": 3}


def test_competitive_comes_from_the_knowledge_base():
    full_kb = load_knowledge_base(KNOWLEDGE_BASE_DIR)
    flat = {i.key: i for i in full_kb.instruments()}
    assert is_competitive(flat["eic-accelerator:eic-accelerator"])
    assert is_competitive(flat["prokilowatt:projekte"])
    assert not is_competitive(flat["lib:lib-beitrag"])


def test_assumed_counts_half(sensora_criteria):
    """hr_luzern is `annahme` in the example: met adds the other half, unknown removes its half."""
    base = muss_met_share(sensora_criteria)
    half = Fraction(1, 2 * 12)  # 12 applicable muss criteria
    assert muss_met_share(_with(sensora_criteria, hr_luzern="erfuellt")) == base + half
    assert muss_met_share(_with(sensora_criteria, hr_luzern="unbekannt")) == base - half


def test_mostly_unknown(sensora_criteria):
    assert not mostly_unknown(sensora_criteria)
    unknown = {c.criterion_id: "unbekannt" for c in sensora_criteria if c.kind == "muss"}
    assert mostly_unknown(_with(sensora_criteria, **unknown))
    # 8 of 12 unknown is exactly two thirds, not more.
    eight = dict(list(unknown.items())[:8])
    assert not mostly_unknown(_with(sensora_criteria, **eight))


def test_advice_after_money_and_floor_after_known():
    ranks = assign_ranks(
        [
            _entry("beratung-gut", "passt_gut", advisory=True),
            _entry("geld-unklar", "passt_mit_anpassung", Fraction(1), mostly_unknown=True),
            _entry("geld-anpassung", "passt_mit_anpassung", Fraction(1, 4)),
            _entry("geld-gut", "passt_gut", Fraction(1, 2)),
        ]
    )
    assert ranks == {"geld-gut": 1, "geld-anpassung": 2, "geld-unklar": 3, "beratung-gut": 4}
