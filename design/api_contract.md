# API contract and dev split

This document fixes the interfaces between frontend, API layer and agent, so that both devs can build in parallel. The architecture is described in [architecture.md](architecture.md).

**Single source of truth:** [contract.schema.json](contract.schema.json) (JSON Schema draft 2020-12). Every shape below is a named definition in it, referenced as `contract.schema.json#/$defs/<Name>`. [examples/](examples/) holds a complete, schema-valid run for the fictional Sensora AG, built from the real LIB data in the knowledge base.

## 1. Who builds what

| Area | Owner | Paths |
|---|---|---|
| Frontend, all 7 screens, live panel, export | Jasper | `frontend/` |
| API layer: FastAPI app, config, routes, SSE, run store, health, programs endpoint | Jasper | `backend/app/main.py`, `config.py`, `api/`, `trace.py` |
| Knowledge base loader | Jasper | `backend/app/knowledge_base/` |
| Agent: all 6 steps, prompts, orchestrator logic | Philipp | `backend/app/agent/`, `backend/app/llm/` |
| Pydantic models mirroring this contract | Philipp | `backend/app/models/` |
| Eval runner and test projects | Philipp | `backend/eval/`, `tests/projects/` |

The seam between the two halves of the backend is the Python interface in section 4. The seam between frontend and backend is the HTTP API in section 2.

**How to stay unblocked:**
- Jasper builds the frontend against the files in `design/examples/` (mock mode that serves them, including replaying `trace_events.json` with delays). The real backend can be switched on later with one setting.
- Philipp builds the agent against the Python interface and tests it with the fake LLM and the examples, without the HTTP layer.
- First integration: the API layer calls the real agent functions instead of returning examples.

**Changing the contract:** edit `contract.schema.json` and the affected examples in the same commit, make sure the examples still validate, and tell the other dev before pushing. No silent shape changes.

## 2. HTTP endpoints

Base path `/api`. JSON in and out, UTF-8. All user-facing texts in responses are German (Swiss spelling).

| Method | Path | Request | Response | Notes |
|---|---|---|---|---|
| GET | `/api/health` | | `Health` | `llm_available: false` if no API key or provider unreachable |
| GET | `/api/programs` | | `ProgramSummary[]` | includes invalid files with their validation errors |
| POST | `/api/profile` | `ProfileRequest` | `ProfileResponse` | Step 1. `needs_clarification` if the input is too vague |
| POST | `/api/questions` | `QuestionsRequest` | `QuestionSet` | Steps 3 and 2. Empty `questions` with `skip_reason` means: skip Screen 3 |
| POST | `/api/runs` | `RunRequest` | `RunCreated` (202) | Applies answers, starts steps 3 to 6 in the background |
| GET | `/api/runs/{run_id}` | | `RunResult` | Partial while `status` is `laeuft` |
| GET | `/api/runs/{run_id}/events` | | SSE stream of `TraceEvent` | See section 3 |
| POST | `/api/runs/{run_id}/retry` | `RetryRequest` | 202, empty body | Re-checks one instrument with status `fehler` |

Optional, if time allows (shapes to be added to the contract when built): `POST /api/runs/{run_id}/chat` for the follow-up chat, `GET /api/runs/{run_id}/export.pdf`.

**Errors:** every non-2xx response has the body `ApiError` (`code`, German `message`).

| HTTP | `code` | When |
|---|---|---|
| 400 | `ungueltige_eingabe` | request does not match the contract |
| 404 | `run_nicht_gefunden` | unknown `run_id` |
| 409 | `pruefung_laeuft` | retry on an instrument that is not in status `fehler` |
| 502 | `ki_antwort_ungueltig` | LLM output failed validation twice |
| 503 | `ki_nicht_verfuegbar` | no API key or provider down |

## 3. Live trace (SSE)

`GET /api/runs/{run_id}/events` returns `text/event-stream`:

```
id: 6
event: instrument_started
data: {"run_id":"run_8f3a2c","seq":6,"ts":"2026-10-23T21:40:01Z","type":"instrument_started","message":"Prüfe Luzerner Innovationsbeitrag.","data":{...}}
```

- `id` is `seq`, `event` is `type`, `data` is the full `TraceEvent` as JSON on one line.
- A client that reconnects with `Last-Event-ID: <seq>` gets all events with a higher `seq` replayed first. A client that connects late gets all events from `seq` 1.
- The server closes the stream after `run_completed` or `run_failed`.
- After a retry, the stream of that run emits `instrument_started`, `instrument_completed` or `instrument_failed`, then `plan_ready` again. The client then reloads `GET /api/runs/{run_id}`.

Event types (all in `TraceEvent`, discriminated by `type`):

| `type` | `data` |
|---|---|
| `run_started` | `programs`, `instruments` |
| `step_started` | `step`: `vorfilter`, `pruefung`, `bewertung`, `fahrplan` |
| `step_completed` | `step`, `duration_ms` |
| `prefilter_result` | `kept` (instrument refs), `rejected` (`Rejected[]`) |
| `instrument_started` | `program_id`, `instrument_id`, `program_name`, `instrument_name` |
| `instrument_completed` | `program_id`, `instrument_id`, `fit`, `badges` (counts of ✓ ~ ? ✗), `duration_ms` |
| `instrument_failed` | `program_id`, `instrument_id`, `error`, `retryable` |
| `plan_ready` | `timeline_entries`, `warnings` |
| `run_completed` | `duration_ms`, `fits` (count per fit level) |
| `run_failed` | `error` |

## 4. Python interface (API layer ↔ agent)

Owned by Philipp in `backend/app/agent/__init__.py`, called by the API layer. All models are the Pydantic versions of the contract definitions with the same names.

```python
async def extract_profile(req: ProfileRequest, kb: KnowledgeBase, llm: LLMClient) -> ProfileResponse: ...

async def build_questions(profile: ProjectProfile, kb: KnowledgeBase, llm: LLMClient) -> QuestionSet: ...

def apply_answers(profile: ProjectProfile, answers: list[Answer]) -> ProjectProfile: ...

async def run_analysis(
    run_id: str,
    profile: ProjectProfile,
    kb: KnowledgeBase,
    llm: LLMClient,
    emit: Callable[[TraceEvent], None],
    today: date,
) -> RunResult: ...

async def retry_instrument(
    result: RunResult,
    ref: InstrumentRef,
    kb: KnowledgeBase,
    llm: LLMClient,
    emit: Callable[[TraceEvent], None],
    today: date,
) -> RunResult: ...
```

- The API layer owns run ids, the run store, the SSE queue and `emit`. The agent only calls `emit` and returns results.
- `KnowledgeBase` (from the loader) exposes `programs: list[Program]`, `get(program_id)`, `instruments()` yielding `(program, instrument)` pairs, and `invalid: list[InvalidFile]`.
- `today` is passed in so that deadline logic is testable.

## 5. Data definitions

All in [contract.schema.json](contract.schema.json). The essentials:

### ProjectProfile
- `input_text`: the user's original text. `summary`: one German sentence.
- `fields`: map of profile field name to `ProfileField`. Field names are the ones used in `criteria[].profile_fields` of the knowledge base; the core list with value types is in `x-core-fields` in the schema.
- `ProfileField`: `value`, `status` (`angegeben` = stated by the user, `annahme` = inferred, `fehlt` = missing), `origin` (`text`, `formular`, `rueckfrage`, `korrektur`), `quote` (the user's words for `origin: text`), `note`.
- `value` is `null` exactly when `status` is `fehlt`.
- `applicant_type`, `art_des_vorhabens`, `branche` and `partner` hold arrays of the knowledge base enums (`filter.applicant_types`, `filter.project_types`, `filter.sectors`, `filter.required_partners`), so the pre-filter can compare directly.

### QuestionSet
- At most 3 `Question`s. Each has the `profile_field` it fills, German `text`, `why` ("Warum wir fragen"), button `options`, and `affects`: the criteria whose state can change.
- Answers come back in `RunRequest.answers` and are written into the profile with `origin: rueckfrage`. "Weiss nicht" leaves the field at `fehlt`.

### RunResult
- `matches`: one `InstrumentMatch` per instrument that passed the pre-filter.
- `rejected`: instruments dropped by the pre-filter, with German `reason` and the `rule` that applied: `verfuegbarkeit`, `kanton`, `gesuchsteller`, `vorhaben`, `branche`, `mitarbeitende`, `unternehmensalter` (see [architecture.md](architecture.md#step-3-pre-filter-pure-code)). For `verfuegbarkeit`, `availability_status` and `next_round` are set, so the UI can show "Runde geschlossen, nächste Runde ab ...". Missing required partners are not a reject reason; they appear as a criterion with `scope: filter` and a gap of type `anpassung`.
- `plan`: `FundingPlan`, `null` while running.
- `disclaimer`: always "Orientierungshilfe, keine verbindliche Beurteilung".
- `today`: the reference date for all deadline logic.

### InstrumentMatch
- Display data copied from the knowledge base: names, provider, level, purpose, `funding_summary`, `deadline` (`type`, `rule`, `next_date`), `links`, `source_checked`.
- `status`: `ausstehend`, `laeuft`, `fertig`, `fehler`.
- `fit`: `passt_gut`, `passt_mit_anpassung`, `passt_nicht`; `null` until scored or on `fehler`. `rank` is 1-based within all fitting instruments.
- `criteria`: one `CriterionResult` per criterion (program-wide ones with `scope: programm`, required-partner checks generated from `filter.required_partners` with `scope: filter`).
- `gaps`: what is missing or what would make it fit (see below).

### CriterionResult

| `state` | Badge | Meaning |
|---|---|---|
| `erfuellt` | ✓ | met, backed by profile evidence |
| `annahme` | ~ | probably met, based on an assumption |
| `unbekannt` | ? | not enough information |
| `nicht_erfuellt` | ✗ | not met, backed by profile evidence |
| `nicht_anwendbar` | (hidden or greyed out) | the criterion's `applies_if` condition does not apply |

`evidence` lists the profile field names the state is based on. It is never empty for `erfuellt` or `nicht_erfuellt`. `source` gives title, URL and locator for the "Quelle" link.

### Gap
- `type`: `anpassung` (a `muss` criterion is not met, and a lever could change that) or `infos_fehlen` (information is missing).
- `lever`: the lever text from the knowledge base, or `null`. Never invented.
- `hint`: the German hint written in step 6, or `null`.

### FundingPlan
- `timeline`: entries in phases `jetzt`, `vor_projektstart`, `gesuch`, each with `date` (computed by code) or `date_rule` (rule text from the knowledge base) and an `action`.
- `warnings`: combination warnings (`ausgeschlossen`, `abzug`, `bedingt`) between fitting instruments, with source.
- `next_steps`: checklist items with optional link and due date.
- `contacts`: contact points from the knowledge base, used especially when nothing fits.

## 6. Example run

[examples/](examples/) contains one consistent run for the fictional Sensora AG (Emmen, 18 employees, optical sensor prototype, 18 months, CHF 400,000):

| File | Definition |
|---|---|
| `profile_response.json` | `ProfileResponse` |
| `question_set.json` | `QuestionSet` (3 questions taken from the LIB criteria) |
| `run_request.json` | `RunRequest` with answers |
| `run_result.json` | `RunResult`: LIB `passt_mit_anpassung`, two energy measures rejected by the pre-filter |
| `trace_events.json` | `TraceEvent[]` for the same run |

The example only uses programs that are already in the knowledge base. It is a fixture for development, not a statement about the eligibility of any real company.

Validate the examples (from the repo root):

```powershell
python -c "import json,glob,os,jsonschema;from referencing import Registry,Resource;s=json.load(open('design/contract.schema.json',encoding='utf-8'));r=Registry().with_resource('contract.schema.json',Resource.from_contents(s));m={'profile_response':'ProfileResponse','question_set':'QuestionSet','run_request':'RunRequest','run_result':'RunResult','trace_events':'TraceEvent'};L=lambda y:y if isinstance(y,list) else [y];[print(f,'OK' if not [e for d in L(json.load(open(f,encoding='utf-8'))) for e in jsonschema.Draft202012Validator({'$ref':'contract.schema.json#/$defs/'+m[os.path.basename(f)[:-5]]},registry=r,format_checker=jsonschema.FormatChecker()).iter_errors(d)] else 'FAIL') for f in glob.glob('design/examples/*.json')]"
```
