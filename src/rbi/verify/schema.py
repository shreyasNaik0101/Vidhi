"""Result of an independent verification of one parsed operation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Verdict = Literal["confirm", "correct", "reject"]


@dataclass
class VerifyResult:
    op_seq: int
    verdict: Verdict
    notes: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    est_cost_usd: float = 0.0
