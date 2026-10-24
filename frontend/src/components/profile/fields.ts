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
  | { kind: "multi"; options: Option[]; placeholder?: string; hint?: string; wide?: boolean }
  | { kind: "combo"; options: string[]; placeholder: string }
  | { kind: "yesno"; placeholder?: string }
  | { kind: "date"; placeholder?: string };

export type SectionId = "unternehmen" | "vorhaben" | "finanzen" | "gebaeude" | "weitere";

const opts = (pairs: [string, string][]): Option[] => pairs.map(([id, label]) => ({ id, label }));

/*
 * Option ids are the knowledge base values the backend compares with (knowledge_base/schema/program.schema.json,
 * filter.applicant_types, project_types, sectors, required_partners). A value that is not in the schema is
 * rejected by the backend with 400, so these lists must not contain anything else.
 */

const KANTONE = opts([
  ["LU", "Luzern"], ["AG", "Aargau"], ["AI", "Appenzell Innerrhoden"], ["AR", "Appenzell Ausserrhoden"], ["BE", "Bern"], ["BL", "Basel-Landschaft"],
  ["BS", "Basel-Stadt"], ["FR", "Freiburg"], ["GE", "Genf"], ["GL", "Glarus"], ["GR", "Graubünden"], ["JU", "Jura"], ["NE", "Neuenburg"],
  ["NW", "Nidwalden"], ["OW", "Obwalden"], ["SG", "St. Gallen"], ["SH", "Schaffhausen"], ["SO", "Solothurn"], ["SZ", "Schwyz"],
  ["TG", "Thurgau"], ["TI", "Tessin"], ["UR", "Uri"], ["VD", "Waadt"], ["VS", "Wallis"], ["ZG", "Zug"], ["ZH", "Zürich"],
]);

const APPLICANT_TYPES = opts([
  ["unternehmen", "Unternehmen"], ["kmu", "KMU"], ["startup", "Startup"], ["grossunternehmen", "Grossunternehmen"], ["gemeinde", "Gemeinde"],
  ["verein_stiftung", "Verein oder Stiftung"], ["forschungsinstitution", "Forschungsinstitution"], ["eigentuemer", "Gebäudeeigentümer"],
  ["privatperson", "Privatperson"],
]);

const PROJECT_TYPES = opts([
  ["forschung", "Forschung"], ["entwicklung", "Entwicklung"], ["prototyp", "Prototyp"], ["machbarkeitsstudie", "Machbarkeitsstudie"],
  ["prozessinnovation", "Prozessinnovation"], ["organisationsinnovation", "Organisationsinnovation"], ["klinische_studie", "Klinische Studie"],
  ["digitalisierung", "Digitalisierung"], ["gebaeudesanierung", "Gebäudesanierung"], ["heizungsersatz", "Heizungsersatz"],
  ["erneuerbare_energie", "Erneuerbare Energie"], ["energieeffizienz", "Energieeffizienz"], ["e_mobilitaet", "E-Mobilität"],
  ["nachhaltiges_bauen", "Nachhaltiges Bauen"], ["klimaschutz", "Klimaschutz"], ["investition", "Investition"], ["finanzierung", "Finanzierung"],
  ["wachstum", "Wachstum"], ["gruendung", "Gründung"], ["nachfolge", "Nachfolge"], ["export", "Export"], ["tourismus", "Tourismus"],
  ["regionalentwicklung", "Regionalentwicklung"], ["weiterbildung", "Weiterbildung"], ["kultur", "Kultur"], ["soziales", "Soziales"],
  ["gesundheit", "Gesundheit"],
]);

const SECTORS = opts([
  ["industrie", "Industrie"], ["gewerbe", "Gewerbe"], ["bau", "Bau"], ["handel", "Handel"], ["dienstleistung", "Dienstleistung"], ["ict", "ICT"],
  ["energie", "Energie"], ["gesundheit", "Gesundheit"], ["bildung", "Bildung"], ["tourismus", "Tourismus"], ["hotellerie", "Hotellerie"],
  ["gastronomie", "Gastronomie"], ["landwirtschaft", "Landwirtschaft"], ["kultur", "Kultur"],
]);

const PARTNERS = opts([
  ["forschungspartner", "Forschungspartner (Hochschule, Forschungsinstitution)"], ["umsetzungspartner", "Umsetzungspartner"],
  ["internationaler_partner", "Internationaler Partner"], ["mehrere_betriebe", "Mehrere Betriebe"], ["gemeinde", "Gemeinde"],
]);

/** Shown in the profile header (initial, company name from page 1, Rechtsform), so not repeated as a field. */
export const HEADER_FIELDS = ["rechtsform"];

export const SECTIONS: { id: SectionId; fields: string[] }[] = [
  { id: "vorhaben", fields: ["art_des_vorhabens", "vorhaben_beschreibung", "budget", "laufzeit", "projektstart", "partner"] },
  {
    id: "unternehmen",
    fields: ["standort_gemeinde", "standort_kanton", "handelsregister", "raeumlichkeiten", "mitarbeitende", "unternehmensalter", "applicant_type", "branche", "taetigkeit"],
  },
  { id: "finanzen", fields: ["revisionsart", "nachhaltigkeitsbericht", "umsatz", "geschaeftsjahr"] },
  { id: "gebaeude", fields: ["baujahr", "eigentum_gebaeude", "bestehende_heizung"] },
];

export const FIELD_SPEC: Record<string, FieldSpec> = {
  rechtsform: { kind: "combo", options: RECHTSFORMEN, placeholder: "z. B. AG" },
  standort_gemeinde: { kind: "combo", options: GEMEINDEN, placeholder: "Gemeinde suchen" },
  standort_kanton: { kind: "select", options: KANTONE },
  handelsregister: { kind: "select", options: opts([["LU", "Kanton Luzern"], ["anderer_kanton", "Anderer Kanton"], ["kein_eintrag", "Nicht eingetragen"]]) },
  raeumlichkeiten: { kind: "yesno" },
  mitarbeitende: { kind: "number", suffix: "Personen", placeholder: "z. B. 18", maxDigits: 6 },
  unternehmensalter: { kind: "number", suffix: "Jahre", placeholder: "z. B. 5", maxDigits: 3 },
  applicant_type: { kind: "multi", placeholder: "Art des Gesuchstellers wählen", options: APPLICANT_TYPES },
  branche: { kind: "multi", placeholder: "Branchen wählen", options: SECTORS },
  taetigkeit: { kind: "text", placeholder: "z. B. Entwicklung von Sensoren" },
  art_des_vorhabens: {
    kind: "multi",
    placeholder: "Art des Vorhabens wählen",
    options: PROJECT_TYPES,
    hint: "Bestimmt, welche Förderangebote geprüft werden. Bitte prüfen und ergänzen.",
    wide: true,
  },
  vorhaben_beschreibung: { kind: "textarea", placeholder: "Was möchten Sie umsetzen?" },
  budget: { kind: "number", prefix: "CHF", placeholder: "400'000" },
  laufzeit: { kind: "number", suffix: "Monate", placeholder: "z. B. 18", maxDigits: 3 },
  projektstart: { kind: "date" },
  partner: { kind: "multi", placeholder: "Keine Partner", options: PARTNERS },
  revisionsart: {
    kind: "select",
    options: opts([["ordentlich", "Ordentliche Revision"], ["eingeschraenkt", "Eingeschränkte Revision"], ["opting_out", "Keine Revision (Opting-out)"], ["keine", "Keine Revisionspflicht"]]),
  },
  nachhaltigkeitsbericht: { kind: "yesno" },
  umsatz: { kind: "number", prefix: "CHF", placeholder: "2'500'000" },
  geschaeftsjahr: { kind: "text", placeholder: "z. B. 2025" },
  baujahr: { kind: "number", placeholder: "z. B. 1985", maxDigits: 4 },
  eigentum_gebaeude: { kind: "yesno" },
  bestehende_heizung: { kind: "select", options: opts([["Öl", "Öl"], ["Gas", "Gas"], ["Elektro", "Elektroheizung"], ["Holz", "Holz"], ["Wärmepumpe", "Wärmepumpe"], ["Fernwärme", "Fernwärme"]]) },
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
