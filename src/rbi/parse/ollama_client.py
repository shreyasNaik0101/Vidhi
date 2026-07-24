"""Ollama client for local models — always through the cache and ledger (CLAUDE.md §7).

Local models are free, so no spend guard is needed, but calls are still cached
(a warm re-run costs ~nothing) and recorded (call counts feed the cost table).
num_ctx is set explicitly — never rely on Ollama's default (CLAUDE.md §3).
"""
from __future__ import annotations

import httpx

from ..config import config
from ..llm.cache import ResponseCache
from ..llm.ledger import CostLedger


class OllamaError(RuntimeError):
    pass


def generate(
    prompt: str,
    *,
    model: str,
    stage: str,
    num_ctx: int | None = None,
    num_predict: int = 1024,
    temperature: float = 0.0,
    fmt: str | None = "json",
    cache: ResponseCache | None = None,
    ledger: CostLedger | None = None,
    timeout: float = 600.0,
) -> str:
    """Return the model's text. Cache hit -> no network call.

    fmt="json" uses Ollama's grammar-constrained decoding so output is always
    syntactically valid JSON — no more delimiter/truncation parse failures.
    num_predict bounds output length; generation dominates CPU latency.
    """
    num_ctx = config.ollama_num_ctx if num_ctx is None else num_ctx
    params = {
        "num_ctx": num_ctx,
        "num_predict": num_predict,
        "temperature": temperature,
        "format": fmt,
    }
    cache = cache or ResponseCache()
    ledger = ledger or CostLedger()

    hit = cache.get(model, prompt, params)
    if hit is not None:
        ledger.record(
            model=model, stage=stage, input_tokens=0, output_tokens=0,
            est_cost_usd=0.0, cache_hit=True,
        )
        return hit

    body: dict = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "temperature": temperature,
        },
    }
    if fmt:
        body["format"] = fmt

    try:
        resp = httpx.post(
            f"{config.ollama_host}/api/generate",
            json=body,
            timeout=timeout,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise OllamaError(f"Ollama call failed for model {model!r}: {e}") from e

    data = resp.json()
    text = data.get("response", "")
    ledger.record(
        model=model,
        stage=stage,
        input_tokens=int(data.get("prompt_eval_count", 0)),
        output_tokens=int(data.get("eval_count", 0)),
        est_cost_usd=0.0,  # local model
        cache_hit=False,
    )
    cache.put(model, prompt, text, params)
    return text
