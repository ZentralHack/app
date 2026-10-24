"""Anonymised log of chat questions for the canton insights: which offer, what was asked,
how well it could be answered. No profile data, no run id."""

import json
from datetime import UTC, datetime
from pathlib import Path


def log_question(
    path: Path | None, program_id: str, instrument_id: str, question: str, basis: str
) -> None:
    """Appends one JSON line. `path` None turns the log off."""
    if path is None:
        return
    entry = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "program_id": program_id,
        "instrument_id": instrument_id,
        "question": question,
        "basis": basis,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")
