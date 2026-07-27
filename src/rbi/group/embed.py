"""Local embeddings via Ollama (PROJECT_SPEC.md §6.7). Free; cached; through the ledger.

Precompute one vector per operation, then cluster on cosine. Falls back cleanly:
callers that want a purely deterministic run use word_similarity instead.
"""
from __future__ import annotations

import json
from typing import Callable

import httpx

from ..config import config
from ..llm.cache import ResponseCache
from ..llm.ledger import CostLedger
from .models import OpRef
from .similarity import cosine

DEFAULT_EMBED_MODEL = "nomic-embed-text-v2-moe:latest"


def embed_text(
    text: str,
    *,
    model: str = DEFAULT_EMBED_MODEL,
    cache: ResponseCache | None = None,
    ledger: CostLedger | None = None,
    timeout: float = 120.0,
) -> list[float]:
    cache = cache or ResponseCache()
    ledger = ledger or CostLedger()
    params = {"embed": True}

    hit = cache.get(model, text, params)
    if hit is not None:
        ledger.record(model=model, stage="group", input_tokens=0, output_tokens=0,
                      est_cost_usd=0.0, cache_hit=True)
        return json.loads(hit)

    resp = httpx.post(
        f"{config.ollama_host}/api/embed",
        json={"model": model, "input": text},
        timeout=timeout,
    )
    resp.raise_for_status()
    vector = resp.json()["embeddings"][0]
    ledger.record(model=model, stage="group", input_tokens=0, output_tokens=0,
                  est_cost_usd=0.0, cache_hit=False)
    cache.put(model, text, json.dumps(vector), params)
    return vector


def embedding_similarity_fn(
    ops: list[OpRef], *, model: str = DEFAULT_EMBED_MODEL
) -> Callable[[str, str], float]:
    """Precompute embeddings for all op texts; return a cosine similarity(a,b)."""
    vectors = {op.text: embed_text(op.text, model=model) for op in ops}
    return lambda a, b: cosine(vectors[a], vectors[b])
