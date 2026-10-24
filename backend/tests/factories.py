"""Test profiles. Sensora AG comes from design/examples, edge cases follow tests/projects."""

import json
from typing import Any

from app.config import REPO_DIR
from app.models.contract import ProfileField, ProjectProfile


def field(value: Any, status: str = "angegeben") -> ProfileField:
    if value is None:
        status = "fehlt"
    return ProfileField(value=value, status=status, origin=None, quote=None, note=None)


def make_profile(text: str = "Testvorhaben", **fields: Any) -> ProjectProfile:
    """Keyword values become `angegeben` fields; pass a ProfileField for anything else."""
    return ProjectProfile(
        input_text=text,
        summary=text,
        fields={k: v if isinstance(v, ProfileField) else field(v) for k, v in fields.items()},
    )


def sensora_profile() -> ProjectProfile:
    """The example profile before the questions (design/examples/profile_response.json)."""
    path = REPO_DIR / "design" / "examples" / "profile_response.json"
    return ProjectProfile.model_validate(json.loads(path.read_text(encoding="utf-8"))["profile"])


def aarau_profile() -> ProjectProfile:
    """tests/projects/ausserhalb-luzern.json"""
    return make_profile(
        "KMU aus Aarau, Drucksensor-Prototyp mit Fachhochschule",
        standort_kanton=field("AG", "annahme"),
        standort_gemeinde="Aarau",
        applicant_type=field(["unternehmen", "kmu"], "annahme"),
        art_des_vorhabens=["entwicklung", "prototyp"],
        mitarbeitende=30,
        budget=500000,
        partner=["forschungspartner"],
    )


def treuhand_profile() -> ProjectProfile:
    """tests/projects/kein-passendes-programm.json: company event, no project type fits."""
    return make_profile(
        "Treuhandbüro in Kriens, Firmenausflug und Kundenfest zum Jubiläum",
        standort_kanton=field("LU", "annahme"),
        standort_gemeinde="Kriens",
        applicant_type=field(["unternehmen", "kmu"], "annahme"),
        art_des_vorhabens=["kultur"],
        vorhaben_beschreibung="Firmenausflug und Kundenfest zum 20-Jahr-Jubiläum",
        branche=["dienstleistung"],
        mitarbeitende=8,
        budget=30000,
    )


def vague_profile() -> ProjectProfile:
    """tests/projects/zu-vage.json"""
    return make_profile(
        "Wir brauchen Geld für unser Unternehmen.",
        art_des_vorhabens=None,
        vorhaben_beschreibung=None,
    )
