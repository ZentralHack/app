import { useState } from "react";
import { api, ApiRequestError } from "./api";
import type { Clarification, InstrumentRef, ProfileField, ProjectProfile, QuestionSet } from "./api/contract";
import { Sidebar } from "./components/layout/Sidebar";
import { Alert } from "./components/ui/Alert";
import { useRun } from "./hooks/useRun";
import { parseChf } from "./lib/format";
import { CaptureScreen, type CaptureDraft } from "./screens/CaptureScreen";
import { PlanScreen } from "./screens/PlanScreen";
import { ProfileScreen } from "./screens/ProfileScreen";
import { ProgramScreen } from "./screens/ProgramScreen";
import { QuestionsScreen } from "./screens/QuestionsScreen";
import { ResultsScreen } from "./screens/ResultsScreen";
import { TraceScreen } from "./screens/TraceScreen";
import { t } from "./text/de-CH";

type Step = 1 | 2 | 3 | 4 | 5 | 6;
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
 */
export function App() {
  const [step, setStep] = useState<Step>(1);
  const [reachable, setReachable] = useState<Step>(1);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<CaptureDraft>(EMPTY_DRAFT);
  const [clarification, setClarification] = useState<Clarification | null>(null);
  const [profile, setProfile] = useState<ProjectProfile | null>(null);
  const [questions, setQuestions] = useState<QuestionSet | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [runId, setRunId] = useState<string | null>(null);
  const [openProgram, setOpenProgram] = useState<InstrumentRef | null>(null);
  // The company name is only shown in the UI; it is not part of the profile the backend checks.
  const [company, setCompany] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const run = useRun(runId);

  function go(next: Step) {
    setError(null);
    setStep(next);
    setOpenProgram(null);
    setReachable(r => (next > r ? next : r));
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
    return p;
  }

  async function launchRun(p: ProjectProfile, qs: QuestionSet | null, given: Record<string, string>) {
    const list = (qs?.questions ?? [])
      .filter(q => given[q.id])
      .map(q => ({ question_id: q.id, profile_field: q.profile_field, answer: given[q.id] }));
    const { run_id } = await api.startRun({ profile: p, answers: list });
    setRunId(run_id);
  }

  const analyse = () =>
    withBusy(async () => {
      if (await createProfile(draft)) advance(2);
    });

  const confirmProfile = () =>
    withBusy(async () => {
      if (!profile) return;
      const qs = await api.buildQuestions(profile);
      setQuestions(qs);
      if (qs.questions.length) advance(3);
      else {
        await launchRun(profile, qs, {});
        advance(4);
      }
    });

  const startRun = () =>
    withBusy(async () => {
      if (!profile) return;
      await launchRun(profile, questions, answers);
      advance(4);
    });

  /** Roadmap: only steps already reached can be opened. */
  const navigate = (target: Step) => {
    if (target <= reachable) go(target);
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
    setCompany(null);
    setReachable(1);
    go(1);
  }

  const match = openProgram && run.result?.matches.find(m => m.program_id === openProgram.program_id && m.instrument_id === openProgram.instrument_id);

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <Sidebar step={step} reachable={reachable} onNavigate={n => navigate(n as Step)} />
      <div className="flex min-w-0 flex-1 flex-col">
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
        {step === 2 && profile && <ProfileScreen profile={profile} company={company} onChange={updateField} busy={busy} onBack={() => go(1)} onConfirm={confirmProfile} />}
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
          <ProgramScreen
            match={match}
            result={run.result}
            onEditProfile={() => go(2)}
            onBack={() => {
              setOpenProgram(null);
              window.scrollTo({ top: 0 });
            }}
          />
        )}
        {step === 5 && !match && (
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
        {step === 6 && <PlanScreen result={run.result} onEditProfile={() => go(2)} onNewProject={reset} />}
      </div>
    </div>
  );
}
