"""Allowed values for the profile fields the pre-filter compares with `instrument.filter`."""

from typing import get_args

from app.models.program import ApplicantType, ProjectType, RequiredPartner, Sector

PROFILE_ENUMS: dict[str, frozenset[str]] = {
    "applicant_type": frozenset(get_args(ApplicantType)),
    "art_des_vorhabens": frozenset(get_args(ProjectType)),
    "branche": frozenset(get_args(Sector)),
    "partner": frozenset(get_args(RequiredPartner)),
}
