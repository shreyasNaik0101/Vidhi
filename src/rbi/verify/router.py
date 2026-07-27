"""Routing: which parsed operations get an independent second check (CLAUDE.md §6.5).

Only the uncertain middle band (0.5–0.9) is routed, plus a small random sample of
high-confidence ops for calibration. Anything already 'unresolved' is skipped —
it has already abstained. This keeps the paid verifier off the easy cases.
"""
from __future__ import annotations

import random

from ..parse.schema import Operation

LOW = 0.5
HIGH = 0.9


def needs_verify(op: Operation, *, sample_rate: float = 0.10, rng: random.Random | None = None) -> bool:
    if op.operation == "unresolved":
        return False
    if LOW <= op.confidence < HIGH:
        return True                      # the genuinely uncertain band
    if op.confidence >= HIGH:
        r = rng or random
        return r.random() < sample_rate  # calibration sample of confident parses
    return False                         # < 0.5 is downgraded upstream
