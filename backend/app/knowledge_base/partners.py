"""Required partners (`filter.required_partners`) as generated `muss` criteria.

A missing partner never drops an instrument in the pre-filter. It becomes a criterion
with scope `filter` that the user can fix; the lever text is fixed here, one per enum value.
"""

from app.models.program import Criterion, Instrument, RequiredPartner

PREFIX = "partner_"

_TEXTS: dict[RequiredPartner, tuple[str, str]] = {
    "forschungspartner": (
        "Ein Forschungspartner (Hochschule oder Forschungsinstitution) ist beteiligt.",
        "Forschungspartner beiziehen",
    ),
    "umsetzungspartner": ("Ein Umsetzungspartner ist beteiligt.", "Umsetzungspartner beiziehen"),
    "internationaler_partner": (
        "Ein internationaler Partner ist beteiligt.",
        "Internationalen Partner beiziehen",
    ),
    "mehrere_betriebe": (
        "Mehrere Betriebe sind am Vorhaben beteiligt.",
        "Weitere Betriebe ins Vorhaben einbinden",
    ),
    "gemeinde": ("Eine Gemeinde ist am Vorhaben beteiligt.", "Gemeinde ins Vorhaben einbinden"),
}
_LEVERS = {f"{PREFIX}{partner}": lever for partner, (_, lever) in _TEXTS.items()}


def partner_criteria(instrument: Instrument) -> list[Criterion]:
    return [
        Criterion(
            id=f"{PREFIX}{partner}",
            text=_TEXTS[partner][0],
            kind="muss",
            about="partner",
            profile_fields=["partner"],
            source=instrument.source,
        )
        for partner in instrument.filter.required_partners
    ]


def partner_lever(criterion_id: str) -> str | None:
    """Fixed lever text for a generated partner criterion."""
    return _LEVERS.get(criterion_id)
