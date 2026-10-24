/* How each profile field is edited and where it sits. Fields not listed here fall back to a text input under "Weitere Angaben". */
import { GEMEINDEN } from "../../content/gemeinden";
import { RECHTSFORMEN } from "../../content/rechtsformen";

export interface Option {
  id: string;
  label: string;
}

export type FieldSpec =
  | { kind: "text"; placeholder: string }
  | { kind: "textarea"; placeholder: string }
  | { kind: "number"; placeholder: string; prefix?: string; suffix?: string; maxDigits?: number }
  | { kind: "select"; options: Option[]; placeholder?: string }
  | { kind: "multi"; options: Option[]; placeholder?: string }
  | { kind: "combo"; options: string[]; placeholder: string }
  | { kind: "yesno"; placeholder?: string }
  | { kind: "date"; placeholder?: string };

export type SectionId = "unternehmen" | "vorhaben" | "finanzen" | "gebaeude" | "weitere";

const opts = (pairs: [string, string][]): Option[] => pairs.map(([id, label]) => ({ id, label }));

const KANTONE = opts([
  ["LU", "Luzern"], ["ZG", "Zug"], ["NW", "Nidwalden"], ["OW", "Obwalden"], ["SZ", "Schwyz"], ["UR", "Uri"], ["AG", "Aargau"], ["BE", "Bern"], ["ZH", "Zürich"],
]);

/** Shown in the profile header (initial, name, Rechtsform), so not repeated as fields. */
export const HEADER_FIELDS = ["unternehmensname", "rechtsform"];

export const SECTIONS: { id: SectionId; fields: string[] }[] = [
  {
    id: "unternehmen",
    fields: ["standort_gemeinde", "standort_kanton", "handelsregister", "mitarbeitende", "unternehmensalter", "applicant_type", "branche", "taetigkeit", "raeumlichkeiten", "traegerschaft", "sitz_schweiz_uid"],
  },
  { id: "vorhaben", fields: ["vorhaben_beschreibung", "art_des_vorhabens", "budget", "laufzeit", "projektstart", "partner", "neue_arbeitsplaetze"] },
  { id: "finanzen", fields: ["revisionsart", "nachhaltigkeitsbericht", "umsatz", "umsatz_mind_100k", "kreditwuerdig", "geschaeftsjahr"] },
  { id: "gebaeude", fields: ["baujahr", "eigentum_gebaeude", "bestehende_heizung", "flaeche_daemmung", "pv_leistung", "eigenverbrauch", "co2_befreit"] },
];

export const FIELD_SPEC: Record<string, FieldSpec> = {
  unternehmensname: { kind: "text", placeholder: "z. B. Muster AG" },
  rechtsform: { kind: "combo", options: RECHTSFORMEN, placeholder: "z. B. AG" },
  standort_gemeinde: { kind: "combo", options: GEMEINDEN, placeholder: "Gemeinde suchen" },
  standort_kanton: { kind: "select", options: KANTONE },
  handelsregister: { kind: "select", options: opts([["LU", "Kanton Luzern"], ["andere", "Anderer Kanton"], ["keiner", "Nicht eingetragen"]]) },
  mitarbeitende: { kind: "number", suffix: "Personen", placeholder: "z. B. 18", maxDigits: 6 },
  unternehmensalter: { kind: "number", suffix: "Jahre", placeholder: "z. B. 5", maxDigits: 3 },
  applicant_type: {
    kind: "multi",
    placeholder: "Art des Gesuchstellers wählen",
    options: opts([["unternehmen", "Unternehmen"], ["kmu", "KMU"], ["startup", "Startup"], ["gemeinde", "Gemeinde"], ["verein", "Verein"], ["privatperson", "Privatperson"]]),
  },
  branche: {
    kind: "multi",
    placeholder: "Branchen wählen",
    options: opts([["industrie", "Industrie"], ["handwerk", "Handwerk"], ["dienstleistung", "Dienstleistung"], ["ict", "ICT"], ["tourismus", "Tourismus"], ["landwirtschaft", "Landwirtschaft"], ["bau", "Bau"], ["gewerbe", "Gewerbe"], ["holzverarbeitung", "Holzverarbeitung"], ["oeffentlich", "Öffentliche Hand"]]),
  },
  taetigkeit: { kind: "text", placeholder: "z. B. Entwicklung von Sensoren" },
  raeumlichkeiten: { kind: "select", options: opts([["eigene", "Eigene Räume im Kanton"], ["gemietet", "Gemietete Räume im Kanton"], ["keine", "Keine Räume im Kanton"]]) },
  traegerschaft: { kind: "text", placeholder: "z. B. Gemeinde oder Genossenschaft" },
  vorhaben_beschreibung: { kind: "textarea", placeholder: "Was möchten Sie umsetzen?" },
  art_des_vorhabens: {
    kind: "multi",
    placeholder: "Art des Vorhabens wählen",
    options: opts([
      ["forschung", "Forschung"], ["entwicklung", "Entwicklung"], ["prototyp", "Prototyp"], ["markteintritt", "Markteintritt"], ["investition", "Investition"],
      ["sanierung", "Sanierung"], ["gebaeudesanierung", "Gebäudesanierung"], ["daemmung", "Dämmung"], ["heizungsersatz", "Heizungsersatz"], ["photovoltaik", "Photovoltaik"],
      ["umbau", "Umbau"], ["energie", "Energie"], ["regionalentwicklung", "Regionalentwicklung"],
    ]),
  },
  budget: { kind: "number", prefix: "CHF", placeholder: "400'000" },
  laufzeit: { kind: "number", suffix: "Monate", placeholder: "z. B. 18", maxDigits: 3 },
  projektstart: { kind: "date" },
  partner: { kind: "multi", placeholder: "Partner wählen", options: opts([["hochschule", "Hochschule"], ["forschungsinstitut", "Forschungsinstitut"], ["unternehmen", "Unternehmen"]]) },
  neue_arbeitsplaetze: { kind: "text", placeholder: "z. B. 5 bis 10" },
  revisionsart: { kind: "select", options: opts([["ordentlich", "Ordentliche Revision"], ["eingeschraenkt", "Eingeschränkte Revision"], ["keine", "Keine (Opting-out)"]]) },
  nachhaltigkeitsbericht: { kind: "yesno" },
  umsatz: { kind: "number", prefix: "CHF", placeholder: "2'500'000" },
  geschaeftsjahr: { kind: "number", placeholder: "z. B. 2025", maxDigits: 4 },
  baujahr: { kind: "number", placeholder: "z. B. 1985", maxDigits: 4 },
  eigentum_gebaeude: { kind: "select", options: opts([["Eigentum", "Eigentum"], ["Miete", "Miete"]]) },
  bestehende_heizung: { kind: "select", options: opts([["Öl", "Öl"], ["Gas", "Gas"], ["Elektro", "Elektroheizung"], ["Holz", "Holz"], ["Wärmepumpe", "Wärmepumpe"], ["Fernwärme", "Fernwärme"]]) },
  pv_leistung: { kind: "number", suffix: "kWp", placeholder: "z. B. 100", maxDigits: 5 },
  eigenverbrauch: { kind: "yesno" },
  sitz_schweiz_uid: { kind: "yesno" },
  umsatz_mind_100k: { kind: "yesno" },
  kreditwuerdig: { kind: "yesno" },
  co2_befreit: { kind: "yesno" },
  flaeche_daemmung: { kind: "number", suffix: "m²", placeholder: "z. B. 120", maxDigits: 5 },
};

export function specFor(name: string): FieldSpec {
  return FIELD_SPEC[name] ?? { kind: "text", placeholder: "Ergänzen" };
}

/** "neue_halle" → "Neue halle": readable label for a stored value the option list does not know. */
function humanize(value: string) {
  const s = value.replace(/[_-]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Options plus any stored value that is not in the list, so data never disappears from a select. */
export function withValue(options: Option[], values: string[]): Option[] {
  const extra = values.filter(v => !options.some(o => o.id.toLowerCase() === v.toLowerCase())).map(v => ({ id: v, label: humanize(v) }));
  return [...options, ...extra];
}

export function optionId(options: Option[], value: string): string {
  return options.find(o => o.id.toLowerCase() === value.toLowerCase())?.id ?? value;
}
