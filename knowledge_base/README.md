# Wissensbasis

Eine JSON-Datei pro Förderprogramm in `programs/`, validiert gegen [`schema/program.schema.json`](schema/program.schema.json) (Schema v2, eingefroren). Originalquellen liegen in `sources/<id>/`.

## Programm hinzufügen

1. **ID festlegen.** Zuerst in der Tabelle «Program ids» in `CLAUDE.md` eintragen. Kebab-case, nur `a-z`, `0-9` und `-`.
2. **Datei anlegen.** `programs/<id>.json`, Dateiname = `id`. `schema_version` ist `"2.0"`. Vorlage: [`lib.json`](programs/lib.json).
3. **Quellen sichern.** Quell-PDF nach `sources/<id>/` legen. In `sources[]` mit `id`, `title`, `type`, `url`, `version`, `published` und `checked` (Prüfdatum) erfassen, `local_path` als `sources/<id>/<datei>`.
4. **Fundstelle immer setzen.** Jedes Kriterium, jeder Hebel und jede Verfügbarkeit verweist mit `source.source_id` auf eine Quelle. `source.locator` immer ausfüllen: Randnummer, Ziffer, Artikel oder Seite, z. B. `N 51-72` oder `Ziff. 3.3`.
5. **`null` statt raten.** Unbekannte Werte sind `null`. Offene Punkte kommen in `meta.open_questions`.
6. **Verfügbarkeit korrekt setzen.** `availability.status` pro Instrument: `aktiv` (jetzt beantragbar), `geplant`, `runde_geschlossen` oder `eingestellt`. Nur `aktiv` kann ein Treffer werden.
7. **Vorfilter sauber füllen.** `filter.sectors` leer = offen für alle Branchen; nur füllen, wenn die Quelle einschränkt. `filter.required_partners` leer = kein Partner nötig.
8. **Hebel nur aus der Quelle.** `levers` sind die einzigen erlaubten «So wird es passend»-Hinweise. Nichts eintragen, was die Quelle nicht hergibt.
9. **Kombinationsregeln mit kanonischen IDs.** `combination_rules[].with` verwendet nur IDs aus der Tabelle in `CLAUDE.md`.
10. **Status.** `meta.status` bleibt `draft`, bis jemand jedes Feld gegen die Quelle geprüft hat. Dann `verified` mit `verified_by`.

## Vor dem Commit validieren

Im Repo-Root den Validierungsbefehl aus dem [README](../README.md#setup-und-start) ausführen. Jede Datei muss `OK` melden.

Das Schema ändert sich nur, wenn mindestens drei Programme dasselbe neue Feld brauchen.
