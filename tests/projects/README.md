# Test projects

Fictional projects for the eval set. No real companies. Each file is one project with the input the user would type and the result we expect.

## Format

| Field | Meaning |
|---|---|
| `id`, `title` | file name and short German title |
| `category` | `standard` or `edge_case` |
| `input` | a `ProfileRequest` (see `design/contract.schema.json`) |
| `answers` | answers to follow-up questions, by profile field name. Empty means: skip the questions. |
| `expected.needs_clarification` | `true` if the agent must ask what the money is for instead of running |
| `expected.profile` | profile values the agent must extract |
| `expected.programs` | programs that must appear as a fit. `fit` lists the accepted fit levels. `instrument_id: null` means any instrument of the program. `required: false` means a hit is good but a miss is not counted as an error. |
| `expected.rejected` | programs that must not appear as a fit (dropped by the pre-filter or `passt_nicht`) |
| `expected.behaviour` | checks for a human reviewer (German) |
| `meta.status` | `draft` until a researcher has checked the expectations against the sources, then `verified` with `verified_by` |

Expectations for programs that are not yet in `knowledge_base/programs/` stay in the file. The eval runner reports them as "not in knowledge base" instead of as a miss.

## Projects

| File | What it tests |
|---|---|
| `sensor-prototyp.json` | Example from the challenge brief: LIB and Innosuisse |
| `pv-schreinerei.json` | Building and energy: insulation, PV, deadline before construction |
| `tourismus-startup.json` | Tourism and startup support, LIB waiting period for new companies |
| `gemeinde-gewerbehaus.json` | Gemeinde as applicant: energy and regional development |
| `keine-innovation.json` | Buying standard equipment: no innovation programs |
| `zu-vage.json` | Edge case: input too vague |
| `ausserhalb-luzern.json` | Edge case: company outside Kanton Luzern |
| `kein-passendes-programm.json` | Edge case: nothing fits |
| `maschinenbau-bildpruefung.json` | Industry: AI image inspection, no research partner yet (Innosuisse lever) |
| `hotel-weggis-sanierung.json` | Hotel: oil heating to heat pump, facade, rooms, loan (SGH, energy programme) |
| `app-startup-kurz.json` | Edge case: short, messy input from an app start-up |
| `baeckerei-sursee-mundart.json` | Edge case: Swiss German input, bakery oven with waste heat |
| `medtech-zug.json` | Edge case: start-up from Kanton Zug, Luzern programmes must drop |
| `werbekampagne-nichts.json` | Edge case: advertising campaign, nothing fits |
| `coiffeuse-nachfolge.json` | Succession: hairdresser takes over a salon, guarantee for the loan |
| `export-brasilien.json` | Export: protection against non-payment (SERV) |
| `stadt-luzern-mfh-heizung.json` | City of Luzern: gas heating to heat pump plus charging stations |
