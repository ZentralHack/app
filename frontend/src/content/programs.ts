/* Display names for canonical program IDs (see the ID table in CLAUDE.md). */
export const PROGRAM_NAMES: Record<string, string> = {
  lib: "Luzerner Innovationsbeitrag",
  "foerderprogramm-energie-lu": "Förderprogramm Energie",
  innosuisse: "Innosuisse",
  "nrp-luzern": "Neue Regionalpolitik Luzern",
  "startup-luzern": "Startup Luzern",
  itz: "ITZ",
  "bg-mitte": "BG Mitte",
  serv: "SERV",
  "s-ge": "Switzerland Global Enterprise",
  innotour: "Innotour",
  pronovo: "Pronovo",
  klimastiftung: "Klimastiftung Schweiz",
};

export const programName = (id: string) => PROGRAM_NAMES[id] ?? id;
