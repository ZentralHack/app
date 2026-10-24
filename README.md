# FundPilot: Fördermittel-Agent Luzern

**Live-Version:** https://fundpilot-production.up.railway.app · Benutzername: fundpilot / Passwort: adQHVijOoZBSNlB5

Ein KI-Agent, der zu einem konkreten Vorhaben eines Luzerner Unternehmens passende Förderprogramme findet, nachvollziehbar erklärt, warum sie passen und was noch fehlt, und daraus einen Förderfahrplan macht.

![Zentral Hack 2026](https://img.shields.io/badge/Zentral%20Hack-2026-1f6feb)
![Kategorie AI Agentic](https://img.shields.io/badge/Kategorie-AI%20Agentic-8250df)
![Status Prototyp](https://img.shields.io/badge/Status-Prototyp-d97706)

> **Orientierungshilfe, keine verbindliche Beurteilung.**
> Der Agent beurteilt die Förderberechtigung nicht verbindlich und ersetzt weder die Prüfung durch die Förderstelle noch eine Beratung. Alle Unternehmensdaten in diesem Repo sind fiktiv.

## Was FundPilot tut

Förderprogramme für Unternehmen im Kanton Luzern sind über Kanton, Gemeinden, Region, Bund und Stiftungen verteilt. Jedes Programm hat eigene Bedingungen, Fristen und Ausschlüsse. FundPilot nimmt eine Beschreibung des Vorhabens in eigenen Worten entgegen und führt in sechs Schritten zum Ergebnis:

1. **Erfassen:** Vorhaben in 1 bis 3 Sätzen, dazu Gemeinde, Mitarbeitende, Budget.
2. **Profil prüfen:** Jedes Feld ist markiert als *angegeben*, *Annahme* oder *fehlt* und lässt sich korrigieren.
3. **Rückfragen:** Nur Fragen, deren Antwort eine Einstufung ändern kann, höchstens 10, «Weiss nicht» ist immer möglich.
4. **Prüfung live:** Der Agent prüft jedes Kriterium jedes in Frage kommenden Förderangebots und zeigt dabei seine Arbeit.
5. **Ergebnisse:** passt gut / passt mit Anpassung / passt nicht, je mit Kriterien, Belegen, Quellen, Frist und der Förderregel aus der Quelle. Beratungsangebote stehen getrennt als «Begleitende Angebote».
6. **Förderfahrplan:** Was jetzt zu tun ist, was vor Projektstart, was zum Gesuch, mit Fristen, Links, Ansprechstellen und Kombinationshinweisen. Export als PDF über den Browser.

### Was es besonders macht
- **Förderfahrplan statt Liste:** Förderangebote auf einer Zeitachse; was kollidiert, steht beim betroffenen Schritt.
- **«So wird es passend»:** Bei knappen Treffern zeigt der Agent, welche Änderung das Förderangebot erschliesst, z. B. einen Forschungspartner beiziehen. Nur Hebel, die in der Wissensbasis stehen.
- **Einblicke für den Kanton (Konzept):** Eine anonymisierte Auswertung der Anfragen könnte zeigen, was Unternehmen fördern lassen wollen und welche Programme niemand findet. Im Prototyp nicht umgesetzt.

## So arbeitet der Agent

```mermaid
flowchart LR
    A["Vorhaben<br/>(Freitext)"] --> S1
    S1["1 · Profil<br/>LLM"] --> S2["2 · Rückfragen<br/>Code"]
    S2 --> S3["3 · Vorfilter<br/>Code"]
    S3 --> S4["4 · Prüfung pro Kriterium<br/>LLM"]
    S4 --> S5["5 · Bewertung<br/>Code"]
    S5 --> S6["6 · Förderfahrplan<br/>Code + LLM"]
    KB[("Wissensbasis<br/>JSON")] -.-> S2
    FK[("Fragenkatalog<br/>JSON")] -.-> S2
    KB -.-> S3
    KB -.-> S4
    KB -.-> S6

    classDef llm fill:#ede9fe,stroke:#7c3aed,color:#1f2937
    classDef code fill:#dbeafe,stroke:#2563eb,color:#1f2937
    classDef mixed fill:#fef3c7,stroke:#d97706,color:#1f2937
    class S1,S4 llm
    class S2,S3,S5 code
    class S6 mixed
```

| Schritt | Wer | Was passiert |
|---|---|---|
| 1 · Profil | LLM | Freitext wird zu einem strukturierten Profil. Code prüft danach: Ein Zitat für *angegeben* muss wörtlich im Text stehen, sonst wird es zur *Annahme*. Ist kein Zweck erkennbar, fragt der Agent zuerst, wofür das Geld ist. |
| 2 · Rückfragen | Code | Fragen aus einem geprüften Fragenkatalog, ausgewählt nach Wirkung. Kein Modellaufruf. |
| 3 · Vorfilter | Code | Nur aktuell beantragbare Förderangebote; falscher Kanton oder falsche Gemeinde, Gesuchstellertyp, Vorhabenstyp, Branche, Grösse oder Alter fallen mit Begründung weg. Ein fehlender Partner ist nie ein Ausschluss, sondern ein Hebel. |
| 4 · Prüfung | LLM | Ein Aufruf pro Förderangebot, parallel. Jedes Kriterium: erfüllt, Annahme, unbekannt oder nicht erfüllt, mit Begründung und wörtlichem Beleg. |
| 5 · Bewertung | Code | Deterministisch: *passt gut*, *passt mit Anpassung* oder *passt nicht*, dazu die Reihenfolge. |
| 6 · Förderfahrplan | Code + LLM | Code ordnet nach Frist und Phase und prüft Kombinationsregeln. Das LLM formuliert nur die Texte; Code verwirft jede Antwort mit neuen Daten oder fremden Programmen. |

**Grundsätze:** Der Code entscheidet, das LLM liest und formuliert. Ohne Beleg kein ✓. Jede Aussage hat eine Quelle mit Fundstelle. Fristen, Bewertung und Reihenfolge berechnet nie das Modell. Beträge werden nicht berechnet; angezeigt wird die Förderregel aus der Quelle.

| Badge | Bedeutung |
|---|---|
| ✓ | **erfüllt**: im Profil belegt |
| ~ | **Annahme**: plausibel, aber nicht ausdrücklich angegeben |
| ? | **unbekannt**: keine Angabe, Rückfrage oder Klärung nötig |
| ✗ | **nicht erfüllt**: im Profil widerlegt |

## Wissensbasis

37 Förderangebote aus 21 Programmen (im Code: Instrumente), eine JSON-Datei pro Programm in [`knowledge_base/programs/`](knowledge_base/programs/), validiert gegen das [Schema v2](knowledge_base/schema/program.schema.json). Jede Quelle hat Titel, URL und Prüfdatum, jedes Kriterium eine Fundstelle (Randnummer, Ziffer, Seite). Unbekannte Werte sind `null` und werden nicht geraten. Anleitung zum Ergänzen: [`knowledge_base/README.md`](knowledge_base/README.md).

| Programm | Ebene | Anbieter | Förderangebote | Hauptquelle |
|---|---|---|---|---|
| Förderprogramm Energie Kanton Luzern 2026 | Kanton | Kanton Luzern | 6 | [Förderbedingungen 2026](https://uwe.lu.ch/-/media/UWE/Dokumente/Themen/Energie/Foerderprogramm/Foerderbedingungen_Foerderbeitraege.pdf?rev=396129e20de74baf976671d98a672bca) |
| Luzerner Innovationsbeitrag | Kanton | Kanton Luzern | 1 | [Handbuch LIB](https://standortfoerderung.lu.ch/-/media/Standortfoerderung/Dokumente/Handbuch_LIB_2026_10_01.pdf?rev=12a0082f68b34a04a3375117401185d0) |
| Neue Regionalpolitik (NRP) Kanton Luzern 2024 bis 2027 | Kanton | Kanton Luzern | 1 | [NRP-Umsetzungsprogramm](https://regiosuisse.ch/sites/default/files/2024-04/NRP-Umsetzungsporgramm%202024-2027_Luzern.pdf) |
| Steuerliche Innovationsförderung Kanton Luzern | Kanton | Kanton Luzern | 1 | [Luzerner Steuerbuch](https://steuerbuch.lu.ch/band2/unternehmenssteuerrecht/bestimmungen_gemaess_steuerreform_staf) |
| Förderprogramm Energie Stadt Luzern 2026 | Gemeinde | Stadt Luzern | 5 | [Förderhandbuch 2026](https://www.stadtluzern.ch/_rte/publikation/420010) |
| BG Mitte | Region | BG Mitte | 1 | [bgm-ccc.ch](https://www.bgm-ccc.ch/) |
| ITZ InnovationsTransfer Zentralschweiz | Region | ITZ | 1 | [itz.ch](https://www.itz.ch/) |
| Innosuisse | Bund | Innosuisse | 6 | [innosuisse.admin.ch](https://www.innosuisse.admin.ch/de/innovationsprojekte-mit-umsetzungspartner) |
| Pronovo Einmalvergütung Photovoltaik | Bund | Pronovo AG | 3 | [pronovo.ch](https://pronovo.ch/de/foerderung/photovoltaik/) |
| Innotour | Bund | SECO | 1 | [seco.admin.ch](https://www.seco.admin.ch/de/innotour-foerderangebot) |
| PEIK Energieberatung für KMU | Bund | BFE, EnergieSchweiz | 1 | [peik.ch](https://peik.ch/) |
| Pilot-, Demonstrations- und Leuchtturmprogramm | Bund | BFE | 1 | [bfe.admin.ch](https://www.bfe.admin.ch/) |
| ProKilowatt | Bund | BFE | 1 | [prokw.ch](https://www.prokw.ch/) |
| SERV Exportrisikoversicherung | Bund | SERV | 1 | [serv-ch.com](https://www.serv-ch.com/en/services/for-swiss-exporters/) |
| Schweizerische Gesellschaft für Hotelkredit | Bund | SGH | 1 | [sgh.ch](https://sgh.ch/finanzierung/unsere-unterstuetzung) |
| Technologiefonds | Bund | BAFU | 1 | [technologiefonds.ch](https://www.technologiefonds.ch/buergschaften) |
| Umwelttechnologieförderung | Bund | BAFU | 1 | [bafu.admin.ch](https://www.bafu.admin.ch/de/utf) |
| Klimastiftung Schweiz | Stiftung | Klimastiftung Schweiz | 1 | [klimastiftung.ch](https://www.klimastiftung.ch/de/antrag-stellen/) |
| Schweizer Berghilfe | Stiftung | Schweizer Berghilfe | 1 | [berghilfe.ch](https://www.berghilfe.ch/) |
| Bürgschaftsgenossenschaft SAFFA | Privat | SAFFA | 1 | [saffa.ch](https://www.saffa.ch/) |
| EIC Accelerator | International | European Innovation Council | 1 | [eic.ec.europa.eu](https://eic.ec.europa.eu/eic-funding-opportunities/eic-accelerator_en) |

## Getestet

[`tests/projects/`](tests/projects/) enthält 17 fiktive Vorhaben mit erwarteten Förderangeboten und Einstufungen, darunter das Sensor-Beispiel aus der Challenge und Grenzfälle (zu vage, ausserhalb Luzern, kein passendes Förderangebot, Mundart, kurze und unordentliche Eingabe).

Stand 24.10.2026 für die ersten 8 Projekte, je 3 Läufe mit den echten Modellen (`uv run python -m eval.run_eval`):
- 7 von 8 Projekten erfüllen ihre Erwartungen in allen 3 Läufen. Beim Tourismus-Startup weicht das Ergebnis ab, unter anderem weil das Budget unter der Mindestsumme von Innotour liegt.
- Eine Analyse dauert im Median 36 Sekunden (höchstens 50) und kostet rund USD 0.13 an Modellkosten.
- Backend: über 200 automatische Tests ohne API-Schlüssel, `ruff` sauber. Jede API-Antwort und jedes Live-Event wird gegen den Contract geprüft.

## Starten

Voraussetzungen: [uv](https://docs.astral.sh/uv/) (installiert Python 3.13 selbst) und Node 20 oder neuer.

**1. Backend** (Ordner `backend`), Windows PowerShell:
```powershell
uv sync
Copy-Item ..\.env.example .env     # OPENAI_API_KEY, MODEL_EXTRACT, MODEL_REASON eintragen; die Datei wird nie committet
uv run uvicorn app.main:app --port 8000
```
macOS und Linux:
```bash
uv sync
cp ../.env.example .env            # OPENAI_API_KEY, MODEL_EXTRACT, MODEL_REASON eintragen
uv run uvicorn app.main:app --port 8000
```
Ohne Schlüssel laufen Wissensbasis, Rückfragen und Tests; die KI-Schritte antworten mit einer Fehlermeldung.

**Demo ohne Netz:** Die Testprojekte in [`backend/demo/`](backend/demo/) sind als echte Läufe gespeichert. Wer genau ihren Vorhabenstext eingibt, sieht sie mit realistischen Pausen abgespielt:
```powershell
$env:DEMO_REPLAY = "true"; uv run uvicorn app.main:app --port 8000     # macOS/Linux: DEMO_REPLAY=true uv run uvicorn app.main:app --port 8000
```

**2. Frontend** (zweites Terminal, Ordner `frontend`, gleich auf allen Systemen):
```bash
npm install
npm run dev        # http://localhost:5173
```
Vite leitet `/api` an `http://127.0.0.1:8000` weiter.

**Umgebungsvariablen** (`backend/.env`, Vorlage [`.env.example`](.env.example), ohne echte Schlüssel):

| Variable | Bedeutung |
|---|---|
| `OPENAI_API_KEY` | Schlüssel für das Sprachmodell (Pflicht für Profil, Prüfung, Fahrplan-Texte, Chat) |
| `MODEL_EXTRACT`, `MODEL_REASON` | Modell-IDs: klein für das Profil, grösser für Prüfung, Texte und Chat |
| `MAX_CONCURRENCY`, `LLM_TIMEOUT_S` | parallele Prüfungen (Standard 4) und Zeitlimit pro Aufruf (Standard 30 s) |
| `DEMO_REPLAY`, `DEMO_TODAY` | gespeicherte Läufe abspielen; Stichtag für alle Fristen festlegen |
| `CORS_ORIGINS` | erlaubte Frontend-Adressen, wenn nicht über den Vite-Proxy |
| `CHAT_LOG` | Pfad des anonymen Fragen-Logs (Standard `backend/logs/chat_questions.jsonl`) |
| `DEV_PERSIST_RUNS`, `DEV_RUNS_FILE` | nur Entwicklung: fertige Läufe über Neustarts behalten (Standard aus, Datei `~/.fundpilot/runs.json`) |

Im Frontend schaltet `VITE_DEV_TOOLS=true` in `frontend/.env.local` ein Entwicklermenü ein; ohne die Variable ist es nicht im Build.

**Prüfen:**
```bash
uv run pytest                      # Backend-Tests, ohne Schlüssel
uv run ruff check .
uv run python -m eval.run_eval     # alle Testprojekte gegen die echten Modelle
npm run build                      # Frontend: Typprüfung und Build
```

## Architektur

```
frontend/          React 19, Vite, TypeScript, Tailwind CSS v4, HeroUI v3
  src/screens/     ein Screen pro Schritt
  src/api/         Client für die HTTP-API mit Live-Events (Server-Sent Events)
backend/           Python 3.13, FastAPI, Pydantic v2, OpenAI (Structured Outputs)
  app/agent/       die sechs Schritte, Orchestrierung, Bewertung, Fahrplan
  app/llm/         eine Schnittstelle für alle Modellaufrufe, Prompts als Markdown
  app/knowledge_base/  Laden, Prüfen und Indexieren der Wissensbasis und des Fragenkatalogs
  demo/            gespeicherte Läufe für DEMO_REPLAY
  eval/            Eval über alle Testprojekte
knowledge_base/    Programme (JSON), Schema, Fragenkatalog, Quell-PDFs
design/            Architektur, API-Contract (JSON Schema), Beispiel-Lauf
tests/projects/    fiktive Testprojekte mit Erwartungen
```

- Ein Contract für alles: [`design/contract.schema.json`](design/contract.schema.json). Backend-Modelle und Frontend-Typen werden daraus erzeugt.
- Alle Modellausgaben sind strukturiertes JSON und werden validiert. Zwei Modelle: ein kleines für das Profil, ein grösseres für die Prüfung und die Fahrplan-Texte; die Modell-IDs stehen nur in `.env`.
- Details: [`design/architecture.md`](design/architecture.md), [`design/api_contract.md`](design/api_contract.md).

## Grenzen

- **Keine verbindliche Beurteilung.** Die Einstufung ist eine Orientierungshilfe; entscheiden tut die Förderstelle.
- **Auswahl, nicht vollständig.** 37 Förderangebote aus 21 Programmen, nicht alle Angebote in der Schweiz. Förderangebote ausserhalb der Wissensbasis findet der Agent nicht.
- **Datenstand.** Die Programmdaten wurden am 23. und 24.10.2026 aus öffentlichen Quellen erfasst und sind noch nicht alle von Hand gegen die Quelle verifiziert. Programme ändern sich.
- **Keine Beträge.** Der Agent rechnet keine Förderbeträge aus; er zeigt die Regel aus der Quelle.
- **Nicht von den Programmanbietern geprüft.** Die Wissensbasis stammt aus öffentlichen Quellen; keine Förderstelle hat sie bestätigt.
- **LLM-Schwankungen.** Dasselbe Vorhaben kann in einzelnen Kriterien unterschiedlich eingestuft werden; der Eval misst das (siehe oben).
- **Nur im Speicher.** Analysen leben im Arbeitsspeicher des Backends; nach einem Neustart sind sie weg.
- **Kein Login.** Keine Konten, keine gespeicherten Vorhaben; wer den Link zu einer Analyse hat, sieht sie, solange das Backend läuft.
- **Nicht umgesetzt:** Einblicke für den Kanton, Mehrsprachigkeit (Eingaben auf Englisch werden verstanden, die Ausgabe ist Deutsch), Gesuchseinreichung.

## Datenschutz und Quellen

- Nur fiktive Unternehmensdaten. Es werden keine realen Firmen gesucht oder abgefragt.
- Nur öffentliche Programminformationen. Jede Quelle ist mit URL und Prüfdatum in der Programmdatei erfasst.
- Eingaben werden nur für die Analyse an das Sprachmodell geschickt (ohne Speicherung beim Anbieter, `store=false`) und im Prototyp nicht dauerhaft gespeichert. Ausnahme: Fragen im Rückfrage-Chat werden ohne Profil und ohne Personendaten in eine lokale Log-Datei geschrieben (Grundlage für die Einblicke für den Kanton).
- API-Schlüssel gehören in `backend/.env` (siehe `.env.example`) und nie ins Repo.

## Team

| Name | Rolle |
|---|---|
| Philipp | Entwicklung |
| Jasper | Entwicklung |
| Johannes | Research und Wissensbasis |
| Julian | Research und Wissensbasis |

## Lizenz

[MIT](LICENSE)
