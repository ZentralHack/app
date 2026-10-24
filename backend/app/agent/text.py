"""Quote matching: a quote counts if it occurs in a text, ignoring whitespace and case."""

import re


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def occurs(quote: str, text: str) -> bool:
    """`text` must already be squashed when checking many quotes against it."""
    quote = squash(quote)
    return bool(quote) and quote in text
