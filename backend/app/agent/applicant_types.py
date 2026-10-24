"""Applicant types that always include another one, pure code.

The profile step sometimes names only one type ("startup") where the knowledge base lists the
broader one ("unternehmen", "kmu"). The pre-filter compares applicant types literally, so an
instrument for companies would drop a start-up. Same rule as project_types.py: only add an
entry if it holds for every applicant of that type.
"""

from collections.abc import Iterable

IMPLIES: dict[str, frozenset[str]] = {
    # A start-up, a KMU and a large company are all companies.
    "startup": frozenset({"unternehmen"}),
    "kmu": frozenset({"unternehmen"}),
    "grossunternehmen": frozenset({"unternehmen"}),
}

# KMU: fewer than 250 employees (Swiss and EU definition).
KMU_MAX_EMPLOYEES = 249


def with_implied(applicant_types: Iterable[str], employees: int | None) -> set[str]:
    """The given types plus everything they imply; a company with fewer than 250 employees
    is also a KMU."""
    types = set(applicant_types)
    for applicant_type in list(types):
        types |= IMPLIES.get(applicant_type, frozenset())
    if "unternehmen" in types and "grossunternehmen" not in types and employees is not None:
        types.add("kmu" if employees <= KMU_MAX_EMPLOYEES else "grossunternehmen")
    return types
