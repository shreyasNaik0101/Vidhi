"""Golden question schema + loader (PROJECT_SPEC.md §9)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from ..config import GOLDEN_DIR

Category = Literal[
    "lookup", "temporal_trap", "entity_trap", "cross_entity", "non_existent", "cascade"
]
ExpectedStatus = Literal[
    "in_force", "not_yet_in_force", "no_provision", "equivalence", "cascade"
]

# Codes from seed.sql — used to validate the golden set references real entities.
VALID_ENTITY_CODES = {
    "LAB", "RRB", "RCB", "UCB", "AIFI", "NBFC", "SFB", "SCB", "PB", "HFC", "ARC",
}


class GoldenQuestion(BaseModel):
    id: str
    category: Category
    question: str
    entity_type: str | None = None
    md_family: str = "IRACP"
    clause: str | None = None
    as_of: date | None = None
    expected_status: ExpectedStatus
    expected_clause: str | None = None
    expected_entities: list[str] = []
    expected_contains: str | None = None
    reference_entity: str | None = None   # the "given" side of a cross-entity/entity-trap Q
    reference_clause: str | None = None
    note: str = ""


def load_golden(path: Path | None = None) -> list[GoldenQuestion]:
    p = path or (GOLDEN_DIR / "questions.jsonl")
    out: list[GoldenQuestion] = []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        try:
            out.append(GoldenQuestion.model_validate_json(line))
        except Exception as e:
            raise ValueError(f"{p.name} line {i}: {e}") from e
    return out
