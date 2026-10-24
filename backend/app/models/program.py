"""Typed view of a knowledge base file (knowledge_base/schema/program.schema.json, v2).

The JSON Schema stays the contract: files are validated against it before they are
parsed into these models. Optional fields default to null or an empty list, as in
the schema. tests/test_models.py checks that the enum literals match the schema.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ApplicantType = Literal[
    "unternehmen",
    "startup",
    "kmu",
    "grossunternehmen",
    "eigentuemer",
    "gemeinde",
    "verein_stiftung",
    "forschungsinstitution",
    "privatperson",
]
ProjectType = Literal[
    "forschung",
    "entwicklung",
    "prototyp",
    "machbarkeitsstudie",
    "prozessinnovation",
    "organisationsinnovation",
    "klinische_studie",
    "gebaeudesanierung",
    "heizungsersatz",
    "erneuerbare_energie",
    "energieeffizienz",
    "e_mobilitaet",
    "nachhaltiges_bauen",
    "export",
    "tourismus",
    "gruendung",
    "wachstum",
    "regionalentwicklung",
    "digitalisierung",
    "weiterbildung",
    "finanzierung",
    "kultur",
    "soziales",
    "gesundheit",
    "nachfolge",
    "investition",
    "klimaschutz",
]
RequiredPartner = Literal[
    "forschungspartner",
    "umsetzungspartner",
    "internationaler_partner",
    "mehrere_betriebe",
    "gemeinde",
]
Sector = Literal[
    "industrie",
    "gewerbe",
    "handel",
    "gastronomie",
    "hotellerie",
    "tourismus",
    "landwirtschaft",
    "bau",
    "dienstleistung",
    "ict",
    "gesundheit",
    "energie",
    "kultur",
    "bildung",
]
Level = Literal["bund", "kanton", "region", "gemeinde", "stiftung", "privat", "international"]
CriterionKind = Literal["muss", "soll", "bewertung"]
AvailabilityStatus = Literal["aktiv", "geplant", "runde_geschlossen", "eingestellt"]
EntitlementType = Literal["rechtsanspruch_im_budget", "kein_rechtsanspruch", "wettbewerb"]
DeadlineType = Literal[
    "fester_termin_jaehrlich",
    "fester_termin",
    "laufend",
    "vor_projektstart",
    "nach_abschluss",
    "ausschreibung",
    "unbekannt",
]
CombinationType = Literal[
    "abzug", "ausgeschlossen", "erlaubt", "bedingt", "voraussetzung", "empfohlen_vorher"
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceRef(_Model):
    source_id: str
    locator: str | None = None


class Source(_Model):
    id: str
    title: str
    type: Literal[
        "handbuch",
        "verordnung",
        "gesetz",
        "merkblatt",
        "webseite",
        "faq",
        "formular",
        "praesentation",
        "reglement",
        "ausschreibung",
    ]
    url: str
    version: str | None = None
    published: date | None = None
    checked: date
    local_path: str | None = None


class TextWithSource(_Model):
    text: str
    source: SourceRef | None = None


class Provider(_Model):
    name: str
    unit: str | None = None
    url: str | None = None


class Scope(_Model):
    cantons: list[str] = []
    municipalities: list[str] = []
    note: str | None = None


class Entitlement(_Model):
    type: EntitlementType
    note: str | None = None
    source: SourceRef | None = None


class Budget(_Model):
    annual_chf: float | None = None
    year: int | None = None
    oversubscription: (
        Literal["anteilige_kuerzung", "bis_budget_ausgeschoepft", "auswahl", "unbekannt"] | None
    ) = None
    note: str | None = None
    source: SourceRef | None = None


class CriterionQuestion(_Model):
    text: str = ""
    options: list[str] = []


class Criterion(_Model):
    id: str
    text: str
    kind: CriterionKind
    about: Literal[
        "unternehmen", "vorhaben", "kosten", "zeit", "partner", "ort", "dokumente", "objekt"
    ]
    applies_if: str | None = None
    profile_fields: list[str] = []
    question: CriterionQuestion | None = None
    evidence: list[str] = []
    source: SourceRef | None = None
    notes: str | None = None


class EligibleItem(_Model):
    id: str
    name: str
    definition: str | None = None
    examples_positive: list[str] = []
    examples_negative: list[str] = []
    source: SourceRef | None = None


class Document(_Model):
    name: str
    condition: str | None = None
    source: SourceRef | None = None


class Documents(_Model):
    application: list[Document] = []
    completion: list[Document] = []


class Lever(_Model):
    text: str
    affects_criteria: list[str]
    source: SourceRef | None = None


class CombinationRule(_Model):
    with_: str = Field(alias="with")
    type: CombinationType
    text: str
    source: SourceRef | None = None


class Availability(_Model):
    status: AvailabilityStatus
    next_round: date | None = None
    note: str | None = None
    source: SourceRef | None = None


class Recipient(_Model):
    type: Literal["gesuchsteller", "forschungspartner", "dienstleister"]
    note: str | None = None


class Filter(_Model):
    applicant_types: list[ApplicantType]
    employees_min: int | None = None
    employees_max: int | None = None
    company_age_years_max: int | None = None
    project_types: list[ProjectType]
    required_partners: list[RequiredPartner]
    sectors: list[Sector]


class CostCategory(_Model):
    id: str
    name: str
    rate_pct: float | None = None
    definition: str | None = None
    source: SourceRef | None = None


class FundingUnit(_Model):
    unit: str
    condition: str | None = None
    base_chf: float | None = None
    amount_chf: float | None = None


class Cofinancing(_Model):
    required: bool | None = None
    rule: str | None = None


class Funding(_Model):
    model: Literal[
        "prozent_kosten",
        "pauschal",
        "pro_einheit",
        "gestaffelt",
        "gutschrift",
        "kostenbeteiligung",
        "individuell",
    ]
    summary: str
    cost_categories: list[CostCategory] = []
    units: list[FundingUnit] = []
    max_share_of_costs_pct: float | None = None
    min_amount_chf: float | None = None
    max_amount_chf: float | None = None
    cofinancing: Cofinancing | None = None
    deductions: list[TextWithSource] = []
    payout_forms: list[str] = []
    calculation_basis: str | None = None
    example: str | None = None
    source: SourceRef | None = None
    note: str | None = None


class RelativeDeadline(_Model):
    event: (
        Literal[
            "projektstart",
            "baubeginn",
            "installationsbeginn",
            "inbetriebnahme",
            "publikation",
            "gruendung",
        ]
        | None
    ) = None
    direction: Literal["vor", "nach"] | None = None
    offset_days: int | None = None


class DeadlineSpec(_Model):
    type: DeadlineType
    rule: str | None = None
    next_dates: list[date] = []
    relative: RelativeDeadline | None = None
    source: SourceRef | None = None


class Timing(_Model):
    deadline: DeadlineSpec
    assessment_period: str | None = None
    decision_time: str | None = None
    max_duration_months: int | None = None
    repeat_limit: str | None = None
    note: str | None = None


class Links(_Model):
    info: str | None = None
    apply: str | None = None
    form: str | None = None


class Instrument(_Model):
    id: str
    name: str
    description: str | None = None
    keywords: list[str] = []
    instrument_type: Literal[
        "beitrag",
        "steuergutschrift",
        "gutschrift",
        "darlehen",
        "buergschaft",
        "beratung",
        "coaching",
        "stipendium",
        "sonstiges",
        "versicherung",
        "preis",
    ]
    availability: Availability
    recipient: Recipient
    filter: Filter
    eligible_items: list[EligibleItem] = []
    exclusions: list[TextWithSource] = []
    criteria: list[Criterion]
    funding: Funding
    timing: Timing
    documents: Documents | None = None
    obligations: list[TextWithSource] = []
    levers: list[Lever] = []
    links: Links = Links()
    source: SourceRef | None = None


class Application(_Model):
    channel: Literal["online_portal", "email", "post", "mixed", "other"] | None = None
    url: str | None = None
    steps: list[str] = []
    note: str | None = None
    source: SourceRef | None = None


class Contact(_Model):
    name: str | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    url: str | None = None


class LegalBasis(_Model):
    title: str
    ref: str | None = None
    url: str | None = None


class Meta(_Model):
    last_verified: date
    verified_by: str | None = None
    status: Literal["draft", "verified"]
    open_questions: list[str] = []


class Program(_Model):
    schema_version: Literal["2.0"]
    id: str
    name: str
    short_name: str | None = None
    provider: Provider
    level: Level
    scope: Scope
    purpose: str
    entitlement: Entitlement
    budget: Budget | None = None
    general_criteria: list[Criterion] = []
    general_exclusions: list[TextWithSource] = []
    instruments: list[Instrument] = Field(min_length=1)
    combination_rules: list[CombinationRule] = []
    application: Application | None = None
    contacts: list[Contact] = []
    legal_basis: list[LegalBasis] = []
    sources: list[Source] = Field(min_length=1)
    meta: Meta

    def source(self, ref: SourceRef | None) -> Source | None:
        """Resolve a source reference to the program's source entry."""
        if ref is None:
            return None
        return next((s for s in self.sources if s.id == ref.source_id), None)
