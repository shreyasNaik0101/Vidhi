"""Slice the operative section out of a normalised amendment (keeps the prompt short)."""
from __future__ import annotations

import re

_START = re.compile(r"modif(?:y|ies)\s+the\s+Directions\s+as\s+under[:\-]", re.IGNORECASE)
_END = re.compile(r"(?:above\s+)?amendment[^\n]{0,60}?come\s+into\s+force", re.IGNORECASE)


def operative_section(text: str) -> str:
    """Text between 'modifies the Directions as under:' and 'come into force'.

    Falls back to the whole text if the markers are absent — the evidence-span
    validator downstream still guards correctness.
    """
    start = m.end() if (m := _START.search(text)) else 0
    end_m = _END.search(text, start)
    end = end_m.start() if end_m else len(text)
    section = text[start:end].strip()
    return section or text.strip()
