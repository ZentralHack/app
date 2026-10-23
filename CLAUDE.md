# Fördermittel-Agent – Projektkontext

Zentral Hack 2026, HSLU Rotkreuz, 23.–24. Oktober 2026. Challenge "Der KI-Fördermittel-Agent für Luzerner Unternehmen" (Kanton Luzern, Kategorie AI Agentic). Team: 4 Personen, 2 Devs (Philipp, Jasper), 2 Research. Read this file fully before working.

Session start: read `../docs/STATUS.md` for current progress.

## The challenge
Build a working prototype of an AI agent that takes a concrete company project ("Vorhaben"), finds matching funding programs relevant to companies in Kanton Luzern (cantonal, regional, national), and explains them clearly.

Must-haves (from the brief):
1. Capture a concrete project or funding need
2. Identify potentially matching programs
3. Explain traceably why each program fits
4. Show target group, purpose, conditions and deadlines in a structured way
5. Show which information is still missing for a final assessment
6. Clearly separate available information, assumptions and uncertainties

Nice-to-haves: follow-up questions, ranking, links to offices, hints on missing conditions, next steps, deadlines/urgency, comparison, multilingual, export.

Rules:
- Public program information only. Data sources transparent.
- Fictional or anonymised company data only. Never scrape or look up real companies.
- No binding statements about eligibility or entitlement. Always "Orientierungshilfe, keine verbindliche Beurteilung".
- Out of scope: submitting applications, binding advice, legal assessments, covering all programs.
- Tech is free. No API keys provided. Standalone prototype, no canton system integration.

Jury: Innovation 25%, technical quality (code, architecture) 25%, problem solving 20%, pitch 15%, business potential 15%. The jury tests the agent live on a realistic project: relevance of programs, traceability, completeness, quality of next steps.
Deliverables: working prototype, README, 3-minute pitch with 5 slides. Example project from the brief: a Luzern KMU builds a novel sensor for industrial quality control and wants to build and test a prototype. Expected hits: Luzerner Innovationsbeitrag (LIB), Innosuisse (especially with a research partner).

## Key features
1. **Förderfahrplan instead of a list**: sequence programs on a timeline, show what to do now, what later, what collides.
2. **"So wird es passend"**: for near-matches, say what change would unlock the program (e.g. add a research partner). Only from `levers` and `filter.required_partners` in the knowledge base, never invented.
3. **Canton insights**: anonymised aggregate of queries shows the canton what companies try to fund and which programs nobody finds.
Polish: visible ✓ ~ ? ✗ badges per criterion, live trace panel of the agent working, rejected programs shown with reasons.

## Architecture
```
Frontend  →  Agent orchestrator  →  Tools and data
              1 Profile               Knowledge base (JSON files)
              2 Questions             LLM API
              3 Matching              Rule code (filters, dates, scoring)
              4 Plan                  Web check (optional)
Around it: eval set (fictional test projects), anonymised query log
```

Agent steps:
1. **Profile** (LLM): free text → structured project profile. Every field tagged `angegeben` (in the user's words), `annahme` (inferred) or `fehlt`.
2. **Questions** (LLM + code): pick at most 3 questions whose answer changes a fit level. Questions come from `criteria[].question` in the knowledge base. Skip the screen if nothing would change.
3. **Pre-filter** (code only): drops instruments using `availability`, `scope` and `filter`. Reject reasons, checked in this order: `verfuegbarkeit` (status not `aktiv`), `kanton`, `gesuchsteller`, `vorhaben`, `branche` (only if `sectors` is not empty), `mitarbeitende`, `unternehmensalter`. Except for `verfuegbarkeit`, only a known profile value drops; a missing value keeps the instrument. **A missing required partner is never a reject:** each entry in `filter.required_partners` becomes a `muss` criterion (scope `filter`) that is fixable and feeds the "So wird es passend" lever (e.g. "Forschungspartner beiziehen").
4. **Matching** (LLM, one call per instrument, in parallel): check every criterion → `erfuellt` ✓ / `annahme` ~ / `unbekannt` ? / `nicht_erfuellt` ✗, each with a one-line reason and the profile evidence. **Rule: no evidence, no ✓.** If the LLM can't point to profile data, the state is `unbekannt`.
5. **Scoring** (code only, deterministic): any ✗ on a `muss` criterion → "passt nicht", unless a lever or a missing required partner explains it → "passt mit Anpassung". Many ? → "passt mit Anpassung / Infos fehlen". Otherwise "passt gut".
6. **Plan** (code + LLM): code sorts by deadline and urgency and applies combination rules, ignoring rules whose target program or instrument does not exist. LLM writes gap hints (only from `levers` and `required_partners`) and next-step texts.

Principles:
- The LLM never does math or deadline logic. Code does.
- All LLM outputs are structured JSON validated against schemas. Nothing free-form for the frontend to parse.
- Model behind one small interface so it can be swapped in one line. Main model: mid tier (Claude Sonnet 5.5 or GPT-6 Sol). Cheap steps (profile extraction) can use a small model.
- No vector DB. 10–15 programs fit in context. Retrieval only for quoting long source docs (e.g. LIB Handbuch by Randnummer) in the follow-up chat.
- Every claim shown to the user carries a source link and locator.

## Knowledge base
```
knowledge_base/
  schema/program.schema.json     ← JSON Schema (draft 2020-12), the contract
  programs/<id>.json             ← one file per program, validated on load
  sources/<id>/                  ← original PDFs and saved page copies
```
- One file per **program**, containing an `instruments` list. Matching runs per instrument.
- Program level: provider, level, scope, entitlement, budget, general_criteria, general_exclusions, combination_rules, application, contacts, legal_basis, sources, meta.
- Instrument level: keywords, availability, filter (for code pre-filter), eligible_items, exclusions, criteria, funding, timing, documents, obligations, levers, links.
- **Schema v2 is frozen** (`schema_version: "2.0"`). Change it only if 3 or more programs need the same new field.
- `filter.required_partners`: empty = no partner needed; otherwise e.g. `forschungspartner`, `umsetzungspartner`, `mehrere_betriebe`. `filter.sectors`: empty = open to all sectors; filled only if the source restricts it.
- `availability.status`: `aktiv`, `geplant`, `runde_geschlossen`, `eingestellt`. The pre-filter only matches `aktiv`.
- Criterion `kind`: `muss` (knock-out), `soll` (advantage or case-by-case), `bewertung` (quality criterion in competitive selection, e.g. Innosuisse).
- `criteria[].question` feeds the questions step. `criteria[].source.locator` gives Randnummer/Ziffer for traceability. `levers` and `filter.required_partners` are the only allowed "what would make it fit" suggestions.
- Unknown values are `null`, never guessed. `meta.open_questions` lists unresolved points.
- Examples: `lib.json` (LIB, from the Handbuch), `foerderprogramm-energie-lu.json` (6 instruments).

### Program ids (canonical)
Use exactly these ids for file names, `id`, `combination_rules[].with` and test projects. New programs get an id here first.

| id | Program | Status |
|---|---|---|
| `lib` | Luzerner Innovationsbeitrag | done |
| `foerderprogramm-energie-lu` | Förderprogramm Energie Kanton Luzern | done (6 instruments) |
| `innosuisse` | Innosuisse, Schweizerische Agentur für Innovationsförderung | planned |
| `nrp-luzern` | Neue Regionalpolitik (NRP), Umsetzung Kanton Luzern | planned |
| `startup-luzern` | Startup-Förderung der Standortförderung Kanton Luzern | planned |
| `itz` | InnovationsTransfer Zentralschweiz (ITZ) | planned |
| `bg-mitte` | Bürgschaftsgenossenschaft Mitte (BG Mitte) | planned |
| `serv` | Schweizerische Exportrisikoversicherung (SERV) | planned |
| `s-ge` | Switzerland Global Enterprise (S-GE) | planned |
| `innotour` | Innotour (SECO) | planned |
| `pronovo` | Pronovo, Einmalvergütung für Photovoltaikanlagen | planned, only if the LU energy program does not cover PV for companies |
| `klimastiftung-schweiz` | Klimastiftung Schweiz | candidate |
| `gemeinde-<name>` | One offer of a Luzern Gemeinde, e.g. `gemeinde-emmen` | candidate |
| `steuerliche-innovationsfoerderung-lu` | Patentbox and R&D super-deduction, Kanton Luzern | reserved: referenced in `lib.json`, no file planned |

Instrument ids are chosen per file (kebab-case, unique within the program).
- Known open question: LIB FAQ says the R&D tax deduction and LIB can't be combined; Handbuch N 136–141 says the tax saving is deducted. Ask the canton.

Key LIB facts: 30% personnel, 20% investment (depreciation), 10% contract research, 10% other costs, max 50%. Assessed on the financial year two years before the claim year. Deadline 31 January of the claim year; claim years 2026 and 2027 both due 31.01.2027. Requires Luzern Handelsregister, premises and staff in LU, properly audited accounts (ordentliche Revision or SA-CH report), sustainability proof. Mere use of existing software or AI tools does not qualify.

## User flow (7 screens)
Running example: fictional Sensora AG, Emmen, 18 employees, optical sensor prototype, 18 months, CHF 400k.
1. **Projekt erfassen**: one text box, optional Gemeinde, size, budget, 3 example buttons, "Analysieren".
2. **Profil prüfen**: fields tagged Angegeben / Annahme / Fehlt, user can correct, "Stimmt so".
3. **Rückfragen**: max 3 cards with button answers and "Warum wir fragen", "Überspringen" allowed.
4. **Agent arbeitet**: live trace: pre-filter → per-program checks → plan. Failed checks show "Nochmals".
5. **Ergebnisse**: ranked cards in three levels (passt gut / passt mit Anpassung / passt nicht). Each card: provider, purpose, funding, deadline, criteria checklist with badges, missing info, link, source date. Rejects collapsed but visible.
6. **Förderfahrplan**: timeline (Jetzt / vor Projektstart / Gesuch) plus combination warning, next-steps checklist with links.
7. **Export und Rückfragen**: PDF export, new project, edit profile, follow-up chat grounded only in result + knowledge base. Footer disclaimer on every page.

Edge cases that must work: too vague input (ask what the money is for), company outside Luzern (cantonal programs rejected with reason, national ones still shown), no fitting program (say so, show closest rejects, name who to ask).

## Build priorities
- **Must**: Screen 1, 4, 5. Matching on 10–12 programs with badges. Scoring in code.
- **Should**: Screens 2 and 3, gap hints, Förderfahrplan with combination warning. Optional: discovery step that searches official sites for programs not in the knowledge base, shown as "nicht verifiziert".
- **If time**: PDF export, follow-up chat, canton insights page, second language.

## Team
- Research (2): build knowledge base files, verify every field against sources, write test projects with expected answers.
- Devs (2, Philipp and Jasper): agent backend and frontend. Architecture in `design/architecture.md`, dev split and API contract in `design/api_contract.md`.

## Key sources
- LIB page: https://standortfoerderung.lu.ch/LIB
- LIB Handbuch v1.0 (01.10.2026): `knowledge_base/sources/lib/Handbuch_LIB_2026_10_01.pdf`
- LIB sample calculation form: https://standortfoerderung.lu.ch/-/media/Standortfoerderung/Dokumente/Berechnungsformular_LIB_Webinar_Muster.xlsx?rev=bc13c41e2283437e9f687ab8b8cf958a
- Energy program LU 2026: https://uwe.lu.ch/-/media/UWE/Dokumente/Themen/Energie/Foerderprogramm/Foerderbedingungen_Foerderbeitraege.pdf
- Innosuisse ordinance: only the 2017 version was reviewed, used for schema structure only. Take Innosuisse values from current documents.
- Federal KMU funding overview: https://www.kmu.admin.ch

## Validate program files
```
pip install jsonschema
python -c "import json,glob,jsonschema;s=json.load(open('knowledge_base/schema/program.schema.json'));v=jsonschema.Draft202012Validator(s,format_checker=jsonschema.FormatChecker());[print(f,'OK' if not (e:=list(v.iter_errors(json.load(open(f,encoding='utf-8'))))) else [(list(x.path),x.message) for x in e[:5]]) for f in glob.glob('knowledge_base/programs/*.json')]"
```

## Working conventions
- This repo may be shown to the jury. No internal strategy, team notes or private material here. Code, tests and build scripts never reference anything outside this repo.
- Never commit API keys. Use `.env`, which is gitignored.
- Validate every program file against the schema before committing.
- Code is written with AI assistance; keep it clean and readable since code quality is scored.
- UI text in German (Swiss spelling, "ss" not "ß").
