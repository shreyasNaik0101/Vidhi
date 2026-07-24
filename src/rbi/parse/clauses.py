"""Deterministic extraction of a clause's verbatim body from the source section.

The model tells us which clause numbers an operation touches; this pulls each
clause's exact text out of the source, so the stored body is verbatim by
construction (CLAUDE.md §13: prefer deterministic checks over model calls).
"""
from __future__ import annotations

import re

# End a clause body at: the next clause marker (' 68D. '), a closing curly/straight
# quote, or end of string.
_NEXT = r"(?=\s\d+[A-Z]?\.\s|[”\"]|\Z)"


def extract_clause_text(source: str, clause_number: str) -> str | None:
    """Verbatim body of `clause_number` in `source`, or None if not present."""
    pat = re.compile(re.escape(clause_number) + r"\.\s*(.*?)" + _NEXT, re.DOTALL)
    m = pat.search(source)
    if not m:
        return None
    body = re.sub(r"\s+", " ", m.group(1)).strip()
    return body or None
