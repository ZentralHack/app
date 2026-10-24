"""Read access to profile fields. A value counts as known unless the field is `fehlt`."""

from typing import Any

from app.models.contract import ProjectProfile


def known(profile: ProjectProfile, name: str) -> Any | None:
    field = profile.fields.get(name)
    if field is None or field.status == "fehlt":
        return None
    return field.value


def known_set(profile: ProjectProfile, name: str) -> set[str] | None:
    """A known enum array field as a set; None if unknown."""
    value = known(profile, name)
    return None if value is None else set(value)
