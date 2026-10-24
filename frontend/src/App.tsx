import { lazy, Suspense, useEffect, useLayoutEffect, useRef, useState } from "react";
import { api, ApiRequestError } from "./api";
import type { Clarification, InstrumentMatch, InstrumentRef, ProfileField, ProjectProfile, QuestionSet } from "./api/contract";
import { RunUpdated, RunUpdating } from "./components/layout/RunUpdating";
import { Sidebar } from "./components/layout/Sidebar";
import { Alert } from "./components/ui/Alert";
import { setProgramNames } from "./content/programs";
import { useRun } from "./hooks/useRun";
import { parseChf } from "./lib/format";
import { readPlace, writePlace } from "./lib/location";
import { findProgram, fitChange, sameProfile, unansweredQuestions, withFields } from "./lib/runFlow";
import type { EditorAnswer } from "./components/program/ProfileEditor";
import { CaptureScreen, type CaptureDraft } from "./screens/CaptureScreen";
import { PlanScreen } from "./screens/PlanScreen";
import { ProfileScreen } from "./screens/ProfileScreen";
import { ProgramGone, ProgramScreen } from "./screens/ProgramScreen";
import { QuestionsScreen } from "./screens/QuestionsScreen";
import { ResultsScreen } from "./screens/ResultsScreen";
import { TraceScreen } from "./screens/TraceScreen";
import { FIT_LABEL, t } from "./text/de-CH";

type Step = 1 | 2 | 3 | 4 | 5 | 6;

// Developer menu: only in a build with VITE_DEV_TOOLS=true. Otherwise the import is dropped from the bundle.
const DevMenu = import.meta.env.VITE_DEV_TOOLS === "true" ? lazy(() => import("./dev/DevMenu")) : null;

/** Where the user was when they started editing the profile after a result was there. */
interface ReturnTo {
  step: Step;
  program: InstrumentRef | null;
  reachable: Step;
}
const EMPTY_DRAFT: CaptureDraft = {
  name: "",
  rechtsform: "",
  gruendungsjahr: "",
  text: "",
  gemeinde: "",
  mitarbeitende: "",
  budget: "",
};

/**
 * The flow (screen 7 not built yet). Holds the flow state and calls the API; screens only render props
 * and report user actions. Steps open in order: the roadmap only leads back to steps already reached,
 * and changing an earlier step closes the steps after it until it is confirmed again.
 *
 * The profile is the one source of truth. When a run starts, the profile it checks (with the answers
 * applied by the backend) replaces the local copy, so answered Rückfragen are not asked again.
 * Once there is a result, a profile change runs the analysis again in the background: the user stays
 * where they were, sees a compact progress line, and the new result replaces the old one when it is done.
 */
export function App() {
  // A reload with a run in the URL opens that run again (the result comes from GET /api/runs/{id}).
  const [restored] = useState(() => readPlace(window.location.search));
  const [step, setStep] = useState<Step>(() => (restored.run ? (Math.max(restored.step, 4) as Step) : 1));
  const [reachable, setReachable] = useState<Step>(restored.run ? 6 : 1);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<CaptureDraft>(EMPTY_DRAFT);
  const [clarification, setClarification] = useState<Clarification | null>(null);
  const [profile, setProfile] = useState<ProjectProfile | null>(null);
  // The profile as read from the description (plus the form), before any correction: shows contradictions.
  const [extracted, setExtracted] = useState<ProjectProfile | null>(null);
  const [questions, setQuestions] = useState<QuestionSet | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [runId, setRunId] = useState<string | null>(restored.run);
  const [openProgram, setOpenProgram] = useState<InstrumentRef | null>(restored.step === 5 ? restored.program : null);
  // The company name is only shown in the UI; it is not part of the profile the backend checks.
  const [company, setCompany] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nextRunId, setNextRunId] = useState<string | null>(null);
  const [returnTo, setReturnTo] = useState<ReturnTo | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const run = useRun(runId);
  const next = useRun(nextRunId);
  const adopted = useRef<string | null>(null);
  const before = useRef<InstrumentMatch | null>(null);
  const keepScroll = useRef<number | null>(null);

  // Program names for the Rückfragen; without them the ids are shown, so a failure here is not an error.
  useEffect(() => {
    api.listPrograms().then(setProgramNames, () => {});
  }, []);

  // The profile the backend checks (answers applied) becomes the local profile, once per run.
  useEffect(() => {
    if (!runId || adopted.current === runId || run.result?.run_id !== runId) return;
    adopted.current = runId;
    setProfile(run.result.profile);
  }, [runId, run.result]);

  // A re-run in the background replaces the shown result when it is complete; a failed one is dropped.
  useEffect(() => {
    if (!nextRunId) return;
    const r = next.result;
    if (next.view.failed || r?.status === "fehler") {
      setNextRunId(null);
      setNotice(null);
      setError(t.update.failed);
      return;
    }
    // The fetched result decides, not only the event stream: a stream that stalls must not leave the page
    // stuck at "0 von 8 geprüft" while the run is long done.
    const done = r?.run_id === nextRunId && r.status === "fertig" && r.completed_at !== null && r.plan !== null;
    if (!done || !r.plan) return;
    keepScroll.current = window.scrollY;
    const change = openProgram ? fitChange(before.current, findProgram(r, openProgram)) : null;
    setNotice(change?.before && change.after ? t.program.fitChanged(FIT_LABEL[change.before], FIT_LABEL[change.after]) : t.update.done);
    setRunId(nextRunId);
    setNextRunId(null);
  }, [nextRunId, next.view.failed, next.view.finished, next.result, openProgram]);

  // The screen goes into the URL: a new screen is a history entry, a new run of the same screen is not.
  const shown = useRef({ step, openProgram });
  useEffect(() => {
    const url = writePlace({ step, run: runId, program: step === 5 ? openProgram : null });
    if (url === window.location.search) return;
    const moved = shown.current.step !== step || shown.current.openProgram !== openProgram;
    shown.current = { step, openProgram };
    const target = url || window.location.pathname;
    if (moved) window.history.pushState(null, "", target);
    else window.history.replaceState(null, "", target);
  }, [step, runId, openProgram]);

  // Browser back and forward: show the screen from the URL, if it can be shown with what is loaded.
  useEffect(() => {
    const onPop = () => {
      const place = readPlace(window.location.search);
      let target = Math.min(place.step, reachable) as Step;
      if (target === 3 && !questions) target = 2;
      if (target === 2 && !profile) target = 1;
      if (target >= 4 && !runId) target = 1;
      shown.current = { step: target, openProgram: target === 5 ? place.program : null };
      setError(null);
      setNotice(null);
      setStep(target);
      setOpenProgram(target === 5 ? place.program : null);
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [reachable, questions, profile, runId]);

  // The run from the URL no longer exists (e.g. the server restarted): start over with a note.
  useEffect(() => {
    if (!restored.run || runId !== restored.run || !run.error || run.result) return;
    setRunId(null);
    setReachable(1);
    setStep(1);
    setError(t.app.runGone);
  }, [restored.run, runId, run.error, run.result]);

  // Same scroll position after the swap.
  useLayoutEffect(() => {
    if (keepScroll.current === null) return;
    window.scrollTo({ top: keepScroll.current });
    keepScroll.current = null;
  }, [runId]);

  function go(next: Step) {
    setError(null);
    setNotice(null);
    setStep(next);
    setOpenProgram(null);
    setReachable(r => (next > r ? next : r));
    window.scrollTo({ top: 0 });
  }

  /** Opens the profile from a later step; "Stimmt so" leads back there. */
  function editProfile() {
    setReturnTo(rt => rt ?? { step, program: openProgram, reachable });
    go(2);
  }

  /** Back to where the profile edit started, with the steps that were open then. */
  function returnBack() {
    const rt: ReturnTo = returnTo ?? { step: 5, program: null, reachable: 6 };
    setReturnTo(null);
    setError(null);
    setReachable(rt.reachable);
    setStep(rt.step);
    setOpenProgram(rt.program);
    window.scrollTo({ top: 0 });
  }

  /** Continues from a step the user just (re)confirmed; later steps have to be done again. */
  function advance(next: Step) {
    setReachable(next);
    go(next);
  }

  /** An edit on `at` makes everything after it outdated. */
  const reopenFrom = (at: Step) => setReachable(r => (r > at ? at : r));

  /** Runs one user action against the API. A failed request shows its German message above the screen. */
  async function withBusy(work: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await work();
    } catch (e) {
      setError(e instanceof ApiRequestError ? e.message : t.app.unexpectedError);
    } finally {
      setBusy(false);
    }
  }

  /** Sends the draft to the profile step, then adds what the form knows better than the text. */
  async function createProfile(d: CaptureDraft): Promise<ProjectProfile | null> {
    const res = await api.createProfile({
      text: d.text,
      gemeinde: d.gemeinde || null,
      mitarbeitende: parseChf(d.mitarbeitende),
      budget_chf: parseChf(d.budget),
    });
    setClarification(res.clarification);
    if (res.status !== "ok" || !res.profile) return null;
    setCompany(d.name.trim() || null);
    const fields: ProjectProfile["fields"] = { ...res.profile.fields };
    // A Rechtsform from the form wins over one read from the text; without it the text-based value stays.
    if (d.rechtsform.trim()) fields.rechtsform = { value: d.rechtsform.trim(), status: "angegeben", origin: "formular", quote: null, note: null };
    // Gründungsjahr becomes the age in years, which is what the programs check.
    const year = Number(d.gruendungsjahr);
    if (d.gruendungsjahr.length === 4 && year <= new Date().getFullYear())
      fields.unternehmensalter = { value: new Date().getFullYear() - year, status: "angegeben", origin: "formular", quote: null, note: `gegründet ${year}` };
    const p = { ...res.profile, fields };
    setProfile(p);
    setExtracted(p);
    return p;
  }

  async function startRunRequest(p: ProjectProfile, qs: QuestionSet | null, given: Record<string, string>) {
    const list = (qs?.questions ?? [])
      .filter(q => given[q.id])
      .map(q => ({ question_id: q.id, profile_field: q.profile_field, answer: given[q.id] }));
    const { run_id } = await api.startRun({ profile: p, answers: list });
    return run_id;
  }

  async function launchRun(p: ProjectProfile, qs: QuestionSet | null, given: Record<string, string>) {
    setRunId(await startRunRequest(p, qs, given));
  }

  /** A new run with the changed profile; the current result stays visible until it is done. */
  async function launchInBackground(p: ProjectProfile, qs: QuestionSet | null, given: Record<string, string>) {
    const ref = returnTo?.program ?? openProgram;
    const found = ref && run.result ? findProgram(run.result, ref) : null;
    before.current = found?.kind === "match" ? found.match : null;
    setNotice(null);
    setNextRunId(await startRunRequest(p, qs, given));
  }

  /** Whether there is a result the user returns to after a profile change. */
  const hasResult = run.result !== null;

  const analyse = () =>
    withBusy(async () => {
      if (await createProfile(draft)) advance(2);
    });

  const confirmProfile = () =>
    withBusy(async () => {
      if (!profile) return;
      if (run.result && sameProfile(profile, run.result.profile)) {
        returnBack();
        return;
      }
      // After a result, only questions not answered yet; the answers are already in the profile.
      const all = await api.buildQuestions(profile);
      const qs = hasResult ? unansweredQuestions(all, answers) : all;
      setQuestions(qs);
      if (qs.questions.length) advance(3);
      else if (hasResult) {
        await launchInBackground(profile, qs, {});
        returnBack();
      } else {
        await launchRun(profile, qs, {});
        advance(4);
      }
    });

  const startRun = () =>
    withBusy(async () => {
      if (!profile) return;
      if (hasResult) {
        await launchInBackground(profile, questions, answers);
        returnBack();
      } else {
        await launchRun(profile, questions, answers);
        advance(4);
      }
    });

  /**
   * Inline editor on a program page: save, stay, run again in the background. Field edits go into the
   * profile; answers to criterion questions go with the run, exactly like Rückfragen.
   */
  const saveEdits = (changes: Record<string, ProfileField>, edits: EditorAnswer[]) =>
    withBusy(async () => {
      if (!profile) return;
      const p = withFields(profile, changes);
      setProfile(p);
      const given = Object.fromEntries(edits.map(e => [e.question.id, e.answer]));
      setAnswers(a => ({ ...a, ...given }));
      setQuestions(unansweredQuestions(await api.buildQuestions(p), { ...answers, ...given }));
      await launchInBackground(p, { questions: edits.map(e => e.question) as QuestionSet["questions"], skip_reason: null }, given);
    });

  /** Roadmap: only steps already reached can be opened. Profile and Rückfragen after a result are an edit. */
  const navigate = (target: Step) => {
    if (target > reachable) return;
    if (hasResult && (target === 2 || target === 3) && step >= 4) setReturnTo(rt => rt ?? { step, program: openProgram, reachable });
    go(target);
  };

  function updateField(name: string, field: ProfileField) {
    setProfile(p => p && { ...p, fields: { ...p.fields, [name]: field } });
    reopenFrom(2);
  }

  function setAnswer(questionId: string, answer: string | null) {
    setAnswers(prev => {
      const next = { ...prev };
      if (answer === null) delete next[questionId];
      else next[questionId] = answer;
      return next;
    });
    reopenFrom(3);
  }

  function reset() {
    setDraft(EMPTY_DRAFT);
    setClarification(null);
    setProfile(null);
    setQuestions(null);
    setAnswers({});
    setRunId(null);
    setNextRunId(null);
    setReturnTo(null);
    setCompany(null);
    setReachable(1);
    go(1);
  }

  /** Developer menu only: show a step of a stored run, with what that step needs loaded. */
  const devJump = (target: number, program: InstrumentRef | null, id: string) =>
    withBusy(async () => {
      const r = await api.getRun(id);
      setRunId(id);
      setProfile(r.profile);
      setExtracted(r.profile);
      if (target === 3) setQuestions(await api.buildQuestions(r.profile));
      setReachable(6);
      setReturnTo(null);
      setStep(target as Step);
      setOpenProgram(target === 5 ? program : null);
      window.scrollTo({ top: 0 });
    });

  const found = openProgram && run.result ? findProgram(run.result, openProgram) : null;
  const match = found?.kind === "match" ? found.match : null;
  const backToResults = () => {
    setOpenProgram(null);
    setNotice(null);
    window.scrollTo({ top: 0 });
  };

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <Sidebar step={step} reachable={reachable} onNavigate={n => navigate(n as Step)} />
      {DevMenu && (
        <Suspense fallback={null}>
          <DevMenu runId={runId} finished={run.result?.status === "fertig"} onJump={devJump} />
        </Suspense>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        {step >= 5 && (nextRunId ? <RunUpdating view={next.view} /> : notice && <RunUpdated text={notice} onClose={() => setNotice(null)} />)}
        {(error ?? run.error) && (
          <div className="mx-auto w-full max-w-app px-6 pt-6 lg:px-14">
            <Alert tone="error">{error ?? run.error}</Alert>
          </div>
        )}

        {step === 1 && (
          <CaptureScreen
            draft={draft}
            onDraftChange={d => {
              setDraft(d);
              reopenFrom(1);
            }}
            clarification={clarification}
            busy={busy}
            onSubmit={analyse}
          />
        )}
        {step === 2 && profile && (
          <ProfileScreen profile={profile} extracted={extracted} company={company} onChange={updateField} busy={busy} onBack={returnTo ? returnBack : () => go(1)} onConfirm={confirmProfile} />
        )}
        {step === 3 && questions && (
          <QuestionsScreen questions={questions} answers={answers} onAnswer={setAnswer} busy={busy} onBack={() => go(2)} onNext={startRun} />
        )}
        {step === 4 && (
          <TraceScreen
            view={run.view}
            result={run.result}
            onRetry={l => run.retry({ program_id: l.program_id, instrument_id: l.instrument_id })}
            onCancel={() => {
              // There is no cancel endpoint: the run finishes in the background, the next start creates a new run.
              setRunId(null);
              advance(questions?.questions.length ? 3 : 2);
            }}
            onNext={() => go(5)}
          />
        )}
        {step === 5 && match && run.result && (
          <ProgramScreen match={match} result={run.result} extracted={extracted} onEditProfile={editProfile} onSaveEdits={saveEdits} onBack={backToResults} />
        )}
        {step === 5 && found && found.kind !== "match" && (
          <ProgramGone
            text={
              found.kind === "rejected"
                ? t.program.dropped(found.rejected.instrument_name, found.rejected.reason)
                : t.program.droppedUnknown(before.current?.instrument_name ?? openProgram!.instrument_id)
            }
            onBack={backToResults}
          />
        )}
        {step === 5 && !found && (
          <ResultsScreen
            result={run.result}
            company={company}
            onOpen={ref => {
              setOpenProgram(ref);
              window.scrollTo({ top: 0 });
            }}
            onRetry={m => run.retry({ program_id: m.program_id, instrument_id: m.instrument_id })}
            onNext={() => go(6)}
          />
        )}
        {step === 6 && <PlanScreen result={run.result} onEditProfile={editProfile} onNewProject={reset} />}
      </div>
    </div>
  );
}
