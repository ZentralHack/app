"""Project types that always include another one, pure code.

The profile step sometimes names only the narrower type ("prototyp") and not the broader one
it belongs to ("entwicklung"). The pre-filter compares project types literally, so an
instrument for development projects would drop a prototype project. Each entry below says
"a project of type A is always also of type B". Only add an entry if that holds for every
project of type A, not just for most.
"""

from collections.abc import Iterable

IMPLIES: dict[str, frozenset[str]] = {
    # Building and testing a prototype is the development of a new product or process.
    "prototyp": frozenset({"entwicklung"}),
    # A clinical study is research on people; programs list it as a special case of research.
    "klinische_studie": frozenset({"forschung"}),
}


def with_implied(project_types: Iterable[str]) -> set[str]:
    """The given types plus everything they imply (one level is enough for the table above)."""
    types = set(project_types)
    for project_type in list(types):
        types |= IMPLIES.get(project_type, frozenset())
    return types
