"""Prompt files, one Markdown file per step. `{{name}}` placeholders are filled by code."""

from functools import cache
from pathlib import Path

PROMPT_DIR = Path(__file__).parent


@cache
def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")


def render(name: str, **values: str) -> str:
    text = load_prompt(name)
    for key, value in values.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text
