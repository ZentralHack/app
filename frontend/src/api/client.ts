/*
 * The frontend talks to the backend only through this interface. It mirrors the HTTP API in
 * design/api_contract.md; the implementation is api/http.ts.
 */
import type {
  ChatRequest,
  ChatResponse,
  ChatSuggestions,
  InstrumentRef,
  ProgramSummary,
  ProfileRequest,
  ProfileResponse,
  ProjectProfile,
  QuestionSet,
  RetryRequest,
  RunCreated,
  RunRequest,
  RunResult,
  TraceEvent,
} from "./contract";

export interface Api {
  /** GET /api/programs */
  listPrograms(): Promise<ProgramSummary[]>;
  /** POST /api/profile */
  createProfile(req: ProfileRequest): Promise<ProfileResponse>;
  /** POST /api/questions */
  buildQuestions(profile: ProjectProfile): Promise<QuestionSet>;
  /** POST /api/runs */
  startRun(req: RunRequest): Promise<RunCreated>;
  /** GET /api/runs/{id}/events (SSE). Calls onEvent for every event, replaying past ones first. Returns an unsubscribe function. */
  subscribeEvents(runId: string, onEvent: (event: TraceEvent) => void): () => void;
  /** GET /api/runs/{id} */
  getRun(runId: string): Promise<RunResult>;
  /** POST /api/runs/{id}/retry */
  retryInstrument(runId: string, ref: RetryRequest): Promise<void>;
  /** GET /api/runs/{id}/chat/{program_id}/{instrument_id}/suggestions */
  chatSuggestions(runId: string, ref: InstrumentRef): Promise<ChatSuggestions>;
  /** POST /api/runs/{id}/chat/{program_id}/{instrument_id} */
  chat(runId: string, ref: InstrumentRef, req: ChatRequest): Promise<ChatResponse>;
}
