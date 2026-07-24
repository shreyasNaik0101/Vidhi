"""Token pricing. Rates come from pricing.json, never hardcoded constants (CLAUDE.md §7)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..config import config


@lru_cache(maxsize=1)
def _rates(path: str | None = None) -> dict[str, dict[str, float]]:
    p = Path(path) if path else config.bedrock_pricing_path
    data = json.loads(p.read_text(encoding="utf-8"))
    return data["models"]


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost of a single call. Unknown models raise — never silently price at 0."""
    rates = _rates()
    if model not in rates:
        raise KeyError(
            f"No pricing for model {model!r} in pricing.json. "
            "Add it and verify against the AWS pricing page before running."
        )
    r = rates[model]
    return (
        input_tokens / 1_000_000 * r["input_per_1m"]
        + output_tokens / 1_000_000 * r["output_per_1m"]
    )


def is_free(model: str) -> bool:
    r = _rates().get(model)
    return bool(r) and r["input_per_1m"] == 0.0 and r["output_per_1m"] == 0.0
