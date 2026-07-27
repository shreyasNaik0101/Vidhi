"""Deterministic guards on the model's JSON (CLAUDE.md §6.4, §13).

Order matters:
  1. strip markdown fences the model may add despite instructions
  2. parse JSON strictly
  3. require evidence_span to be a VERBATIM substring of the source (whitespace-
     insensitive) — the cheap hallucination guard
  4. gate on confidence — below 0.5 becomes 'unresolved'
  5. fill new_clauses by extracting each clause's body verbatim from the source;
     if a claimed clause number is absent, that too downgrades to 'unresolved'

A downgraded operation becomes 'unresolved' — never dropped, never guessed.
"""
from __future__ import annotations

import json
import re

from .clauses import extract_clause_text
from .schema import NewClause, Operation, ParseResult

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
_CONFIDENCE_FLOOR = 0.5


class ParseError(ValueError):
    """Raised when the model output is not recoverable JSON at all."""


def strip_fences(raw: str) -> str:
    s = _FENCE.sub("", raw.strip())
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1 and end > start:
        return s[start : end + 1]
    return s


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _is_verbatim(evidence: str, source: str) -> bool:
    return bool(evidence.strip()) and _norm_ws(evidence) in _norm_ws(source)


def _downgrade(op: Operation, note: str) -> None:
    op.operation = "unresolved"
    op.confidence = 0.0
    op.new_clauses = []
    op.note = note


def _fill_clause_texts(op: Operation, source: str) -> None:
    """Extract each claimed clause's verbatim body; downgrade if any is missing."""
    built: list[NewClause] = []
    for num in op.clause_numbers:
        text = extract_clause_text(source, num)
        if text is None:
            _downgrade(op, f"clause {num} not found verbatim in source")
            return
        built.append(NewClause(clause_number=num, text=text))
    op.new_clauses = built


def postprocess(raw: str, source: str) -> ParseResult:
    """Validate raw model text against the source it was parsed from."""
    try:
        data = json.loads(strip_fences(raw))
    except json.JSONDecodeError as e:
        raise ParseError(f"model output was not valid JSON: {e}") from e

    result = ParseResult.model_validate(data)

    for op in result.operations:
        if op.operation == "unresolved":
            continue
        if not _is_verbatim(op.evidence_span, source):
            _downgrade(op, "evidence_span not found verbatim in source")
        elif op.confidence < _CONFIDENCE_FLOOR:
            _downgrade(op, f"confidence {op.confidence} below floor {_CONFIDENCE_FLOOR}")
        elif op.operation in ("insert", "substitute") and op.clause_numbers:
            # only insert/substitute introduce new text; an omit just names the clause
            # to remove and does NOT contain its body, so don't try to extract it.
            _fill_clause_texts(op, source)
    return result
