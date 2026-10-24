/* Example projects for the "Beispiel laden" buttons on screen 1. Fictional companies only. Every field is filled. */

const SENSOR_TEXT =
  "Wir sind ein KMU aus Emmen mit 18 Mitarbeitenden. Wir entwickeln einen neuartigen optischen Sensor für die Qualitätskontrolle in der Industrie und wollen in den nächsten 18 Monaten einen Prototyp bauen und bei Pilotkunden testen. Budget rund CHF 400'000. Einen Forschungspartner haben wir noch nicht.";

export const EXAMPLES = [
  {
    label: "Sensor-Prototyp",
    company: "Sensora AG",
    rechtsform: "AG",
    gruendungsjahr: "2016",
    gemeinde: "Emmen",
    mitarbeitende: "18",
    budget: "400'000",
    quick: { sitz_schweiz_uid: "ja", umsatz_mind_100k: "ja", kreditwuerdig: "ja", co2_befreit: "nein" },
    text: SENSOR_TEXT,
  },
  {
    label: "PV-Anlage Schreinerei",
    company: "Schreinerei Tannenholz GmbH",
    rechtsform: "GmbH",
    gruendungsjahr: "1994",
    gemeinde: "Ruswil",
    mitarbeitende: "12",
    budget: "250'000",
    quick: { sitz_schweiz_uid: "ja", umsatz_mind_100k: "ja", kreditwuerdig: "ja", co2_befreit: "nein" },
    text: "Unsere Schreinerei in Ruswil hat 12 Mitarbeitende. Wir wollen nächstes Jahr das Dach unserer Werkstatt sanieren und dämmen und danach eine Photovoltaikanlage mit etwa 100 kWp installieren. Das Gebäude ist von 1985 und gehört uns.",
  },
  {
    label: "Gemeinde-Projekt",
    company: "Gemeinde Musterwil",
    rechtsform: "Öffentlich-rechtlich",
    gruendungsjahr: "1848",
    gemeinde: "Musterwil",
    mitarbeitende: "35",
    budget: "2'800'000",
    quick: { sitz_schweiz_uid: "ja", umsatz_mind_100k: "ja", kreditwuerdig: "ja", co2_befreit: "nein" },
    text: "Wir sind eine Landgemeinde im Kanton Luzern. Wir wollen ein leerstehendes Schulhaus von 1962 zu einem Gewerbehaus mit Werkstätten und Coworking umbauen und die Ölheizung durch eine Wärmepumpe ersetzen.",
  },
] as const;
