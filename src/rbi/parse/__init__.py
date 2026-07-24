"""Stage 5: parse. Amendment operative section -> structured operations (CLAUDE.md §6.4).

The core local-LLM step. Deterministic guards live in postprocess (verbatim
evidence-span check, confidence gating, unresolved path) — these catch more
hallucination than any prompt instruction.
"""
from .clauses import extract_clause_text
from .postprocess import ParseError, postprocess
from .schema import NewClause, Operation, ParseResult
from .section import operative_section

__all__ = [
    "NewClause",
    "Operation",
    "ParseResult",
    "ParseError",
    "postprocess",
    "operative_section",
    "extract_clause_text",
]
