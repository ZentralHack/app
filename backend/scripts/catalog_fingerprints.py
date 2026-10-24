"""Check or update `kb_fingerprint` in knowledge_base/question_catalog.json.

    uv run python -m scripts.catalog_fingerprints         # list outdated entries
    uv run python -m scripts.catalog_fingerprints --write   # update them, review → needs_review

An updated entry must be reviewed again: its criteria changed since the last review.
"""

import json
import sys

from app.config import KNOWLEDGE_BASE_DIR
from app.knowledge_base.catalog import fingerprint
from app.knowledge_base.catalog_loader import CATALOG_FILE
from app.knowledge_base.loader import load_knowledge_base


def main(write: bool) -> int:
    path = KNOWLEDGE_BASE_DIR / CATALOG_FILE
    catalog = json.loads(path.read_text(encoding="utf-8"))
    instruments = list(load_knowledge_base(KNOWLEDGE_BASE_DIR).instruments())
    outdated = []
    for field, entry in catalog.items():
        current = fingerprint(instruments, field)
        if entry["kb_fingerprint"] != current:
            outdated.append(field)
            entry["kb_fingerprint"] = current
            entry["review"] |= {"status": "needs_review", "by": None, "date": None}
    for field in outdated:
        print(f"veraltet: {field}")
    if write and outdated:
        text = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
        path.write_text(text, encoding="utf-8")
        print(f"{len(outdated)} Einträge aktualisiert, bitte neu prüfen.")
    return 1 if outdated and not write else 0


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv[1:]))
