# Architecture

The Fördermittel-Agent takes a free-text description of a company project ("Vorhaben"), checks it against a curated knowledge base of funding programs, and returns a traceable, ranked result with a funding roadmap. This document describes how the system is built. The API and data contracts are in [api_contract.md](api_contract.md).

## 1. Design principles

1. **The LLM reads and writes language. Code decides.** The LLM extracts facts and judges single criteria. Filtering, scoring, ranking, dates and combination rules are deterministic code.
2. **Structured outputs only.** Every LLM call returns JSON that is validated against a Pydantic model. The frontend never parses free text.
3. **No evidence, no ✓.** A criterion is only `erfuellt` if the LLM points to profile data. Code enforces this after every call.
4. **Every claim has a source.** Every criterion shown to the user carries the source link and locator (Randnummer, Ziffer, page) from the knowledge base.
5. **The knowledge base is data, not code.** One JSON file per program, validated against `knowledge_base/schema/program.schema.json` at startup. Adding a program needs no code change.
6. **One model interface.** The model can be swapped in one line of config.
7. **Never binding.** Every result carries "Orientierungshilfe, keine verbindliche Beurteilung".

## 2. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.13, FastAPI, Pydantic v2 | Typed models double as LLM output schemas and API schemas. Async for parallel LLM calls. |
| LLM | OpenAI Python SDK (`AsyncOpenAI`), Responses API with Structured Outputs (strict) and Pydantic output models | Schema-enforced JSON; validated objects instead of string parsing. Anthropic is the fallback behind the same interface. |
| Knowledge base | JSON files + `jsonschema` (draft 2020-12) | Human-editable, reviewable in git, no database needed for 10 to 20 programs. |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS | Fast to build, widely known, good fit for a step-by-step UI with a live panel. |
| API types | OpenAPI from FastAPI, TypeScript types generated with `openapi-typescript` | One source of truth for shapes. Backend and frontend cannot drift apart. |
| Live updates | Server-Sent Events (SSE) | One-way stream of trace events. Simpler than WebSockets. |
| Tooling | `uv`, `ruff`, `pytest`; `eslint`, `prettier` | Fast, standard, low configuration. |

No vector database: 10 to 20 programs fit into the context of a single matching call per instrument. No relational database: runs are kept in memory, the anonymised query log is a JSONL file.

## 3. Repository layout

```
CLAUDE.md
README.md
design/
  architecture.md               this file
  api_contract.md               endpoints and JSON schemas
knowledge_base/
  schema/program.schema.json
  schema/question_catalog.schema.json
  programs/<id>.json
  sources/<id>/                 saved copies of the official sources
  question_catalog.json         one follow-up question per profile field (generated once, reviewed)
  question_catalog_review.md    review table written by the catalog script
tests/
  projects/<name>.json          fictional test projects with expected results
backend/
  pyproject.toml
  app/
    main.py                     FastAPI app, router registration, startup
    config.py                   settings from environment (.env)
    api/
      profile.py                POST /api/profile
      questions.py              POST /api/questions
      runs.py                   POST /api/runs, GET /api/runs/{id}, SSE events, retry
      programs.py               GET /api/programs (knowledge base overview)
    models/                     Pydantic models (the contract)
      profile.py
      questions.py
      match.py
      plan.py
      trace.py
      program.py                typed view of a knowledge base file
    knowledge_base/
      loader.py                 load, validate, index programs and the question catalog at startup
    agent/
      orchestrator.py           runs steps 3 to 6, emits trace events
      profile.py                step 1
      questions.py              step 2 (pure code, picks from the question catalog)
      prefilter.py              step 3 (pure code)
      matching.py               step 4
      scoring.py                step 5 (pure code)
      plan.py                   step 6
    llm/
      client.py                 LLMClient protocol + Anthropic implementation
      fake.py                   deterministic fake for tests
      prompts/                  one Markdown prompt per step
    trace.py                    TraceEmitter (per-run event queue)
    querylog.py                 anonymised aggregate log
  scripts/
    build_question_catalog.py   generates and cross-checks the question catalog (offline)
  tests/
    test_prefilter.py
    test_questions.py
    test_question_catalog.py
    test_scoring.py
    test_plan.py
    test_kb_loader.py
  eval/
    run_eval.py                 runs tests/projects/*.json, prints a report
frontend/
  package.json
  src/
    api/client.ts               typed fetch + SSE helpers
    api/types.gen.ts            generated from OpenAPI, do not edit
    screens/                    one component per screen (1 to 7)
    components/                 Badge, ProgramCard, CriteriaList, TracePanel, Timeline, Disclaimer
    text/de-CH.ts               all UI strings (Swiss German spelling)
```

## 4. Data flow

```
Screen 1 Projekt erfassen
   │  free text + optional Gemeinde, size, budget
   ▼
POST /api/profile ──► Step 1 Profile (LLM, small model)
   │  ProjectProfile: every field tagged angegeben / annahme / fehlt
   ▼
Screen 2 Profil prüfen (user corrects fields)
   ▼
POST /api/questions ──► Step 3 Pre-filter (code) + Step 2 Questions (code, question catalog)
   │  QuestionSet: up to 10 questions, or empty
   ▼
Screen 3 Rückfragen (skippable)
   ▼
POST /api/runs ──► returns run_id, starts orchestrator in the background
GET  /api/runs/{id}/events (SSE)  ──► Screen 4 Agent arbeitet (live trace)
   │   Step 3 Pre-filter  (code)
   │   Step 4 Matching    (LLM, one call per instrument, in parallel)
   │   Step 5 Scoring     (code)
   │   Step 6 Plan        (code + LLM for texts)
   ▼
GET /api/runs/{id} ──► RunResult ──► Screen 5 Ergebnisse, Screen 6 Förderfahrplan, Screen 7 Export
```

The profile is the only state that moves between steps. Each step is a function `input model -> output model`, so each can be tested and re-run alone.

The pre-filter runs before the questions step as well, so questions are only asked for instruments that are still in play.

## 5. Agent steps

| # | Module | Kind | Input | Output | Model |
|---|---|---|---|---|---|
| 1 | `agent/profile.py` | LLM | free text, form fields | `ProjectProfile` | small |
| 2 | `agent/questions.py` | code | profile, remaining instruments, question catalog | `QuestionSet` (max 10) | none |
| 3 | `agent/prefilter.py` | code | profile, all instruments | kept instruments + dropped with reason | none |
| 4 | `agent/matching.py` | LLM | profile, one instrument (+ program `general_criteria`) | `InstrumentCheck` | main |
| 5 | `agent/scoring.py` | code | `InstrumentCheck` list | `MatchResult` list with fit level and rank | none |
| 6 | `agent/plan.py` | code + LLM | match results, knowledge base | `FundingPlan` | main |

### Step 1: Profile
- Extracts the fields named in `criteria[].profile_fields` across the knowledge base (company location, size, legal form, project type, budget, timing, partners, and so on).
- The fields the pre-filter needs are mapped to knowledge base enums: `applicant_type` to `filter.applicant_types`, `art_des_vorhabens` to `filter.project_types`, `branche` to `filter.sectors`, `partner` to `filter.required_partners`.
- Each field has a `value`, a `status` (`angegeben`, `annahme`, `fehlt`) and, for `angegeben`, the quote from the user text.
- If the text is too vague to say what the money is for, the step returns `needs_clarification` with one question instead of a profile.

### Step 2: Questions (pure code)
No LLM call at runtime. Every question comes ready-made from the question catalog (see next section); code only decides which ones to ask.
- Code collects all criteria of the instruments that survived the pre-filter whose `profile_fields` are `fehlt`, or `annahme` if the catalog entry lists `annahme` in `ask_if`.
- One question per profile field, taken from the catalog, so duplicates cannot occur. Criteria that no field question can decide (or that have no `profile_fields`) bring their own `criteria[].question`; the answer is stored as profile field `rueckfrage_<criterion_id>`.
- Points per question: +3 per instrument where it decides a `muss` criterion, +1 for a `soll` criterion, +2 if a lever targets that criterion. Half the points if the field is only `annahme`. "Decides" means the catalog's `decides` table gives at least two different states for that criterion.
- All questions with at least 3 points are asked, highest first, **at most 10**. The cap protects the user, it is not a target. If no question reaches the threshold, the set is empty and Screen 3 is skipped. Questions below the threshold or above the cap show up later as missing information.
- "Warum wir fragen" = the catalog's `why` plus "Entscheidet über: <instrument names>". For `annahme` fields the assumed answer is sent as `prefill`.
- Answers: code maps the chosen label to the catalog `value` (number and date inputs are range-checked) and writes it with `origin: rueckfrage`. "Weiss nicht" leaves the field unchanged. Then the pre-filter runs again; there is only one question round.

### Question catalog (offline, once)
`knowledge_base/question_catalog.json` (schema `knowledge_base/schema/question_catalog.schema.json`) holds exactly one follow-up question per profile field, built so that its answer can decide **every** criterion that uses the field. It is a separate file; program schema v2 stays unchanged.

Entry per field: `text`, `why`, `input` (`auswahl`, `zahl` with `unit`/`min`/`max`, `datum`), `options` (label shown to the user plus the `value` written into the profile, typed like the field; "Weiss nicht" with `value: null` is always present), `ask_if` (`fehlt`, optionally `annahme`), `decides` (per criterion: which option gives which state), `not_decidable` (criteria the question cannot decide, with reason), `kb_fingerprint` (hash of the criteria it was built for), `generated` (model, prompt version, date) and `review` (`draft`, `needs_review`, `verified`, with reviewer and date).

**Generation** (`backend/scripts/build_question_catalog.py`, run by hand, never at runtime): for each profile field (core fields from `x-core-fields` in the contract plus all names in `criteria[].profile_fields`), the `main` model at high effort gets the field definition, the allowed enum values, every criterion that uses the field (text, `kind`, `applies_if`, source locator) and the existing `criteria[].question` as inspiration, and returns one entry as structured output. Prompt rules: one thing per question, plain language for a KMU manager, Sie-form, Swiss spelling, at most 120 characters, neutral, no program names, options mutually exclusive and complete, at most 7 options (otherwise number or date input), fine enough to decide every given criterion (e.g. the source's thresholds), one `decides` row per criterion. The script only regenerates entries whose `kb_fingerprint` no longer matches; verified entries with a matching fingerprint are kept.

**Validation** (no entry reaches the demo without all four):
1. **Code checks** (`validate_question_catalog`, run by the script, in `pytest` and at every server start): schema; coverage (every profile field in the knowledge base has an entry, or every criterion on it has `criteria[].question`); option values match the field type and existing enum values; "Weiss nicht" present, unique labels, 2 to 7 options for `auswahl`, `unit`/`min`/`max` for `zahl`; text ends with "?", at most 120 characters, no "ß", no Du-form, no program names, no internal field names, `why` at most 160 characters; every `muss` criterion on the field appears in `decides` or `not_decidable`, every `decides` row references an existing criterion and yields at least two different states; `kb_fingerprint` current, otherwise the entry is `veraltet` and its review falls back to `draft`.
2. **Independent model cross-check** (in the script): a second call sees only question, options and criteria, not the generator's `decides` table, fills in the decision table itself and rates the question against a fixed checklist (understandable without prior knowledge, one thing per question, options complete and non-overlapping, not leading, consistent with the source). Any mismatch triggers one regeneration with that feedback; if it persists, the entry is marked `needs_review` with the reason.
3. **Human review**: the script writes `knowledge_base/question_catalog_review.md` (question, options, decision table, criterion sources, all findings). Researchers check each row against the source and set `review.status` to `verified` with name and date.
4. **Eval and runtime signals**: test project answers (`tests/projects/*.json`, keyed by profile field) must match a catalog option, and the expected fit levels must be reached through the catalog questions. At runtime, the share of "Weiss nicht" and skips per field, and mismatches between matching results and the `decides` table, are logged; high values send the entry back to review.

At runtime all entries are used, but anything not `verified` is listed on the health endpoint. Before the demo that list must be empty.

### Step 3: Pre-filter (pure code)
Drops instruments using `instrument.availability`, `instrument.filter` and `program.scope`. Rules run in this order, the first match gives the reject reason (`Rejected.rule`):

| Rule | Drops when |
|---|---|
| `verfuegbarkeit` | `availability.status` is not `aktiv`. The reject carries the status and `next_round`, so the UI can say "nächste Runde ab ...". |
| `kanton` | profile canton not in `scope.cantons` (empty list means all of Switzerland) |
| `gesuchsteller` | no profile applicant type in `applicant_types` |
| `vorhaben` | no profile project type in `project_types` |
| `branche` | `sectors` is not empty and no profile sector is in it (empty means open to all sectors) |
| `mitarbeitende` | employee count outside `employees_min` / `employees_max` |
| `unternehmensalter` | company age above `company_age_years_max` |

All rules except `verfuegbarkeit` only drop on a known profile value (`angegeben` or `annahme`). If the value is `fehlt`, the instrument stays in. An empty filter list (`applicant_types`, `project_types`, `sectors`) means no restriction. Every drop carries a German reason, shown under "passt nicht".

`scope.municipalities` is not checked yet: a pre-filter rule for it is needed as soon as a Gemeinde program exists.

**Required partners never drop an instrument.** A missing partner is something the user can change, and the brief's own example (Innosuisse with a research partner) depends on showing it. Instead, code adds one `muss` criterion per entry in `filter.required_partners` (scope `filter`, e.g. "Ein Forschungspartner ist beteiligt.", source = the instrument's source) to the matching input. If it is not met, scoring treats it as fixable: fit `passt_mit_anpassung`, gap `anpassung` with the fixed text for that partner type (e.g. "Forschungspartner beiziehen"). These texts are defined once in code, one per enum value.

### Step 4: Matching (one LLM call per instrument, in parallel)
- Input: the profile and one instrument with its criteria, exclusions and the program's `general_criteria`.
- Output per criterion: `state` (`erfuellt`, `annahme`, `unbekannt`, `nicht_erfuellt`, `nicht_anwendbar`), a one-line German reason, and the profile field ids used as evidence.
- `nicht_anwendbar` is only allowed for criteria with an `applies_if` condition.
- Code post-check: `erfuellt` or `nicht_erfuellt` without evidence is downgraded to `unbekannt`. Unknown criterion ids are dropped and logged.
- Calls run with `asyncio.gather` behind a semaphore (`MAX_CONCURRENCY`, default 4).

### Step 5: Scoring (pure code)
For each instrument:
1. A `muss` criterion `nicht_erfuellt`, with no lever in `levers` that affects it: **passt nicht**.
2. An exclusion or negative example applies: **passt nicht**.
3. A `muss` criterion `nicht_erfuellt` that a lever affects, or a required-partner criterion (scope `filter`) not met: **passt mit Anpassung**, with gap type `anpassung`.
4. More than a third of the applicable `muss` criteria are `unbekannt`: **passt mit Anpassung** ("Infos fehlen").
5. Otherwise: **passt gut**.

Every `unbekannt` criterion gets a gap of type `infos_fehlen`, so "passt gut" never hides an unknown `muss` criterion. Criteria `nicht_anwendbar` are not counted.

Within a level, instruments are ranked by: share of applicable `muss` criteria `erfuellt`, then the nearest deadline, then `entitlement` (`rechtsanspruch_im_budget` before `kein_rechtsanspruch` before `wettbewerb`). `rank` counts only fitting instruments; `passt_nicht` has no rank. The thresholds live in one constants block and are covered by unit tests.

### Step 6: Plan
- Code computes the next deadline per fitting instrument from `timing.deadline` and `today`: the next of `next_dates` for fixed dates, `projektstart` for `vor_projektstart`. LIB: costs of year X are claimed by 31 January X+2 (claim years 2026 and 2027 both by 31.01.2027).
- Code places each fitting instrument in one of three phases: **Jetzt** (levers to act on before any application, and instruments recommended beforehand via `empfohlen_vorher`), **Vor Projektstart** (deadline type `vor_projektstart`), **Gesuch** (all others, sorted by date). An instrument with a `voraussetzung` comes after its prerequisite.
- Code applies `combination_rules` between all fitting instruments and produces warnings (`ausgeschlossen`, `abzug`, `bedingt`). Rules whose `with` target (program or `program:instrument`) does not exist in the knowledge base are ignored and logged, never shown.
- The LLM writes the gap hints, using only the `levers` of that instrument, and short next-step texts per instrument. It gets the computed dates; it never computes dates itself.

### Optional modules
- **Discovery** (`agent/discovery.py`): searches official websites for programs that are not in the knowledge base. Results are shown separately, tagged "nicht verifiziert", and never scored.
- **Follow-up chat**: answers questions grounded only in the run result and the knowledge base files of the matched programs.

## 6. LLM interface

```python
class LLMClient(Protocol):
    async def structured(
        self,
        *,
        task: str,                # "profile", "matching", ... for logging and tracing
        system: str,              # stable prompt, cacheable
        user: str,                # per-call content
        output: type[T],          # Pydantic model
        tier: Literal["main", "small"],
    ) -> T: ...
```

- **Provider:** OpenAI (`LLM_PROVIDER=openai`). The OpenAI client implements the protocol with Structured Outputs in strict mode. Fallback: Anthropic (Claude Sonnet 5.5) behind the same interface, selected by one config value.
- **Models:** the model ids live only in `backend/.env`, never in code. `small` maps to `MODEL_EXTRACT` (profile extraction), `main` to `MODEL_REASON` (matching, plan texts, offline catalog script).
  - Follow-up questions need no model at runtime. The offline catalog script uses `main` at high effort for generation and for the cross-check.
- **Output models** derive from `LLMOutput` and must be valid for strict structured outputs: every field required (no defaults), `null` instead of leaving a field out, `additionalProperties: false`. `strict_json_schema` (in `llm/schema.py`) checks this before every call, also in the fake client.
- **Concurrency and timeout:** `MAX_CONCURRENCY` (default 4) parallel calls, `LLM_TIMEOUT_S` (default 30) per call.
- **Swapping:** a second implementation of the protocol (for example another provider) is selected by one config value. The eval runner can run the test projects against both and compare.
- **Prompts:** one Markdown file per step in `llm/prompts/`. The system prompt holds the fixed rules (states, evidence rule, Swiss German, no binding statements). The instrument JSON and the profile go into the user message.
- **Prompt caching:** the system prompt is identical across all matching calls of a run, so it is marked for caching.
- **Refusals and stop reasons:** the client checks `stop_reason` before reading the output. `refusal` and `max_tokens` become typed errors (see section 7).
- **Logging:** each call logs task, model, latency and token usage. Never the API key, never the user's free text in the query log.

## 7. Error handling

| Failure | Behaviour |
|---|---|
| Invalid knowledge base file | Skipped at startup with a logged validation error. `GET /api/programs` lists it as invalid. The app still starts. |
| LLM output fails validation | One retry with the validation error appended. Then the step fails. |
| One matching call fails or times out (30 s) | Only that instrument gets status `fehler`. The run continues. The UI shows "Nochmals", which calls the retry endpoint for that instrument. |
| Profile step fails | 502 with a German message; the user can resubmit. |
| No API key or provider down | 503 at request time with a German message. Health endpoint shows the LLM as unavailable. |
| Input too vague | Not an error: `needs_clarification` with one question. |
| Question catalog missing or invalid | The app still starts; questions fall back to `criteria[].question`. Logged and shown on the health endpoint. |
| Profile field without catalog entry, or entry outdated (`kb_fingerprint`) | Fallback to `criteria[].question` if present, otherwise no question. Listed on the health endpoint. |
| Answer matches no option or is out of range | 400 `ungueltige_eingabe`, field unchanged. |
| Company outside Kanton Luzern | Not an error: cantonal programs are dropped by the pre-filter with a reason, national programs are still checked. |
| No fitting program | Not an error: the result says so, shows the closest rejects with reasons, and names the contact points from the knowledge base. |

Errors are typed (`KnowledgeBaseError`, `LLMOutputError`, `LLMUnavailableError`, `RefusalError`) and mapped to HTTP responses in one exception handler. No silent fallbacks: a failed check is shown as failed, never as "passt nicht".

## 8. Trace events

The orchestrator emits events into a per-run queue. The SSE endpoint streams them to the live panel on Screen 4. The full event list and schemas are in [api_contract.md](api_contract.md#trace-events).

| Event | When | Panel shows |
|---|---|---|
| `run_started` | run begins | number of programs and instruments |
| `step_started` / `step_completed` | each of steps 3 to 6 | step name, duration |
| `prefilter_result` | after step 3 | kept count, dropped instruments with reason |
| `instrument_started` | a matching call starts | program and instrument name |
| `instrument_completed` | a matching call returns | fit level, badge counts (✓ ~ ? ✗) |
| `instrument_failed` | a matching call fails | error text, "Nochmals" |
| `plan_ready` | after step 6 | number of timeline entries and warnings |
| `run_completed` / `run_failed` | end of run | total duration |

Every event has `run_id`, a sequence number, a timestamp, a German `message` for the panel and a typed `data` object. Events are kept with the run, so a reconnecting client can replay them.

## 9. Quality and testing

- **Unit tests** for all pure code: pre-filter, scoring, timeline, combination rules, knowledge base loader. These run without an API key.
- **Fake LLM** (`llm/fake.py`) returns fixed outputs so the orchestrator and API can be tested end to end offline.
- **Eval set:** `tests/projects/*.json` holds fictional projects with expected programs and fit levels. `backend/eval/run_eval.py` runs them against the real model and reports hits, misses and wrong fit levels.
- **Knowledge base validation** runs in the test suite: every file in `knowledge_base/programs/` must validate.
- **Question catalog validation** runs in the test suite and at startup (`validate_question_catalog`, see step 2). The eval checks that test project answers map to catalog options.
- **Lint and format:** `ruff` (backend), `eslint` and `prettier` (frontend).

## 10. Performance and cost

- Target: Screen 4 completes in under 40 seconds for 10 to 15 instruments.
- Matching runs in parallel with low to medium effort; one call per instrument keeps prompts short and failures isolated.
- The small model handles profile extraction. Follow-up questions cost no model call, however many are asked.
- Token usage per run is logged so cost per run can be measured with the eval set.

## 11. Configuration, privacy and security

- Configuration from environment variables via `.env` (never committed): API key, model ids, concurrency, timeouts.
- Only fictional or anonymised company data. The app does not look up companies.
- The query log stores only aggregated, categorical profile data (project type, canton, size class, matched programs), never the free text.
- Every result page and export carries "Orientierungshilfe, keine verbindliche Beurteilung".
