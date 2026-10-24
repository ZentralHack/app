"""Read access to profile fields. A value counts as known unless the field is `fehlt`."""

from typing import Any

from app.models.contract import ProjectProfile


def known(profile: ProjectProfile, name: str) -> Any | None:
    field = profile.fields.get(name)
    if field is None or field.status == "fehlt":
        return None
    return field.value
