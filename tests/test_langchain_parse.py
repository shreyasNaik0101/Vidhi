"""LangChain parse backend: fast wiring tests + an opt-in live end-to-end test.

The backend switch (PARSE_BACKEND / backend=) routing is covered with stubs so it
runs in the normal suite. The real LCEL-chain-over-local-model parse is slow
(minutes on CPU) and is gated behind RUN_LLM_TESTS=1.
"""
from __future__ import annotations

import os

import pytest

pytest.importorskip("langchain_ollama")  # skip cleanly if LangChain isn't installed

from rbi.parse import runner
from rbi.parse.postprocess import ParseResult


def test_backend_switch_routes_to_langchain(monkeypatch):
    """backend='langchain' delegates to the LangChain backend, passing the model."""
    seen = {}

    def fake(text, *, model=None):
        seen["text"], seen["model"] = text, model
        return ParseResult(operations=[])

    monkeypatch.setattr("rbi.parse.langchain_runner.parse_document_langchain", fake)
    out = runner.parse_document("some text", model="gemma4:latest", backend="langchain")

    assert isinstance(out, ParseResult)
    assert seen == {"text": "some text", "model": "gemma4:latest"}


def test_native_backend_does_not_touch_langchain(monkeypatch):
    """backend='native' resolves without ever calling the LangChain path."""
    def boom(*_a, **_k):
        raise AssertionError("LangChain backend called for a native parse")

    monkeypatch.setattr("rbi.parse.langchain_runner.parse_document_langchain", boom)
    monkeypatch.setattr("rbi.parse.runner.operative_section", lambda t: t)
    monkeypatch.setattr("rbi.parse.runner.generate", lambda *a, **k: '{"operations": []}')

    out = runner.parse_document("x", backend="native")
    assert isinstance(out, ParseResult)


@pytest.mark.skipif(
    os.getenv("RUN_LLM_TESTS") != "1",
    reason="set RUN_LLM_TESTS=1 to run the live local-model parse (slow)",
)
def test_langchain_backend_parses_rrb_live():
    """End-to-end: the LangChain LCEL chain parses the real RRB amendment (68C/68D)."""
    from rbi.config import SAMPLES_DIR
    from rbi.extract.normalise import normalise
    from rbi.extract.pdf import extract_pdf
    from rbi.parse.langchain_runner import parse_document_langchain

    text = None
    for p in sorted(SAMPLES_DIR.glob("*.pdf")):
        t = normalise(extract_pdf(str(p)))
        if "RBI/2026-27/201" in t:
            text = t
            break
    assert text, "RRB sample (RBI/2026-27/201) not found"

    result = parse_document_langchain(text, model="gemma4:latest")
    assert isinstance(result, ParseResult)
    inserts = [o for o in result.operations if o.operation == "insert"]
    assert inserts, f"expected an insert op, got {result}"
    assert any("68C" in o.clause_numbers for o in inserts)
