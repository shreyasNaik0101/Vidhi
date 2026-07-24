"""Output schema for parsed amendment operations (CLAUDE.md §6.4).

The model emits STRUCTURE only — including `clause_numbers`, not clause bodies.
`new_clauses` (number + verbatim text) is filled deterministically in postprocess
by slicing the source; the model never reproduces long text (short output = fast on
CPU, and no truncation or paraphrase of the clause body).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Operationkind = Literal["insert", "substitute", "omit", "unresolved"]


class NewClause(BaseModel):
    clause_number: str
    text: str


class Operation(BaseModel):
    seq: int
    operation: Operationkind
    target_chapter: str | None = None
    target_anchor: str | None = None       # clause the op attaches to; None for chapter-level
    section_heading: str | None = None      # 'B.' / 'E1.'
    clause_numbers: list[str] = Field(default_factory=list)  # from the model
    new_clauses: list[NewClause] = Field(default_factory=list)  # filled from source
    evidence_span: str                       # must be verbatim from source
    confidence: float
    note: str | None = None                  # why downgraded, if unresolved


class ParseResult(BaseModel):
    operations: list[Operation]
