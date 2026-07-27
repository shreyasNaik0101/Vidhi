"""LLM guardrails: cache round-trip, ledger spend cap, pricing, router escalation."""
from __future__ import annotations

import pytest

from rbi.llm.cache import ResponseCache, cache_key
from rbi.llm.ledger import CostLedger, SpendCapExceeded
from rbi.llm.pricing import estimate_cost_usd
from rbi.llm.router import route


@pytest.fixture
def db(tmp_path):
    return tmp_path / "llm_cache.db"


# --- cache ---
def test_cache_miss_then_hit(db):
    c = ResponseCache(db)
    assert c.get("gemma3:4b", "hello") is None
    c.put("gemma3:4b", "hello", "world")
    assert c.get("gemma3:4b", "hello") == "world"


def test_cache_key_sensitive_to_params():
    assert cache_key("m", "p", {"t": 0.0}) != cache_key("m", "p", {"t": 0.5})


# --- pricing ---
def test_local_models_are_free():
    assert estimate_cost_usd("gemma3:4b", 1000, 1000) == 0.0


def test_unknown_model_raises_not_silently_free():
    with pytest.raises(KeyError):
        estimate_cost_usd("no-such-model", 10, 10)


# --- ledger / spend cap ---
def test_guard_blocks_over_cap(db):
    led = CostLedger(db, cap_usd=1.00)
    led.record(
        model="anthropic.claude-3-haiku-20240307-v1:0",
        stage="verify",
        input_tokens=0,
        output_tokens=0,
        est_cost_usd=0.95,
        cache_hit=False,
    )
    with pytest.raises(SpendCapExceeded):
        led.guard(0.10)  # 0.95 + 0.10 > 1.00


def test_cache_hits_do_not_count_as_spend(db):
    led = CostLedger(db, cap_usd=1.00)
    led.record(
        model="anthropic.claude-3-haiku-20240307-v1:0",
        stage="verify",
        input_tokens=999999,
        output_tokens=999999,
        est_cost_usd=5.00,
        cache_hit=True,
    )
    assert led.spend_to_date() == 0.0
    led.guard(0.50)  # must not raise — the $5 was a cache hit


# --- router ---
def test_verify_escalates_on_hard():
    normal = route("verify", "normal")
    hard = route("verify", "hard")
    assert normal != hard


def test_local_tasks_route_to_ollama():
    # routes to whatever the local models are configured to (env can override the spec defaults)
    from rbi.config import config
    assert route("parse") == config.ollama_model_parse
    assert route("classify") == config.ollama_model_extract
