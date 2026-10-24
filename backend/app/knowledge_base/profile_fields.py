"""Value types of the core profile fields (`x-core-fields` in the contract).

Used to check question catalog values and follow-up answers before they are written
into a profile.
"""

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.knowledge_base.enums import PROFILE_ENUMS

CANTONS = frozenset(
    "AG AI AR BE BL BS FR GE GL GR JU LU NE NW OW SG SH SO SZ TG TI UR VD VS ZG ZH".split()  # noqa: SIM905
)
MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?$")

type Kind = Literal["text", "integer", "number", "boolean", "enum", "enum_list", "month"]


@dataclass(frozen=True)
class FieldType:
    kind: Kind
    allowed: frozenset[str] = frozenset()

    def accepts(self, value: Any) -> bool:
        match self.kind:
            case "text":
                return isinstance(value, str) and bool(value.strip())
            case "integer":
                return isinstance(value, int) and not isinstance(value, bool)
            case "number":
                return isinstance(value, int | float) and not isinstance(value, bool)
            case "boolean":
                return isinstance(value, bool)
            case "enum":
                return value in self.allowed
            case "enum_list":
                return isinstance(value, list) and all(v in self.allowed for v in value)
            case "month":
                return isinstance(value, str) and MONTH.match(value) is not None


TEXT = FieldType("text")

FIELD_TYPES: dict[str, FieldType] = {
    "standort_kanton": FieldType("enum", CANTONS),
    "standort_gemeinde": TEXT,
    **{name: FieldType("enum_list", allowed) for name, allowed in PROFILE_ENUMS.items()},
    "vorhaben_beschreibung": TEXT,
    "taetigkeit": TEXT,
    "rechtsform": TEXT,
    # Canton of the entry, or one of two answers the question catalog needs.
    "handelsregister": FieldType("enum", CANTONS | {"anderer_kanton", "kein_eintrag"}),
    "raeumlichkeiten": FieldType("boolean"),
    "mitarbeitende": FieldType("integer"),
    "unternehmensalter": FieldType("integer"),
    "umsatz": FieldType("number"),
    "geschaeftsjahr": TEXT,
    "revisionsart": FieldType(
        "enum", frozenset({"ordentlich", "eingeschraenkt", "opting_out", "keine"})
    ),
    "nachhaltigkeitsbericht": FieldType("boolean"),
    "budget": FieldType("number"),
    "laufzeit": FieldType("integer"),
    "projektstart": FieldType("month"),
    "baujahr": FieldType("integer"),
    "bestehende_heizung": TEXT,
    "eigentum_gebaeude": FieldType("boolean"),
}
