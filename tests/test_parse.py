"""Parse stage — deterministic guard tests on recorded model output (no live model).

The verbatim evidence-span check, confidence gating, fence stripping and the
unresolved path are all validated here without touching Ollama, so the suite is
green regardless of which models are pulled. A live smoke test is included but
skips when the configured parse model is absent.
"""
from __future__ import annotations

import json
import re

import httpx
import pytest


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

from rbi.config import SAMPLES_DIR, config
from rbi.extract.normalise import normalise
from rbi.extract.pdf import extract_pdf
from rbi.parse.postprocess import ParseError, postprocess, strip_fences
from rbi.parse.section import operative_section


@pytest.fixture(scope="module")
def rrb_section() -> str:
    for p in sorted(SAMPLES_DIR.glob("*.pdf")):
        t = normalise(extract_pdf(p))
        if "RBI/2026-27/201" in t:
            return operative_section(t)
    raise AssertionError("RRB sample not found")


def _model_json(evidence: str, confidence: float = 0.94, clauses=("68C", "68D")) -> str:
    return json.dumps(
        {
            "operations": [
                {
                    "seq": 1,
                    "operation": "insert",
                    "target_chapter": "V",
                    "target_anchor": None,
                    "section_heading": "B.",
                    "clause_numbers": list(clauses),
                    "evidence_span": evidence,
                    "confidence": confidence,
                }
            ]
        }
    )


# --- section extraction ---
def test_section_bounds(rrb_section):
    assert "68C." in rrb_section and "68D." in rrb_section
    assert "inserted in Chapter V" in rrb_section
    assert "come into force" not in rrb_section


# --- happy path: model gives structure, clause bodies extracted verbatim ---
def test_happy_path(rrb_section):
    res = postprocess(_model_json("The following shall be inserted in Chapter V"), rrb_section)
    op = res.operations[0]
    assert op.operation == "insert"
    assert op.target_chapter == "V"
    assert [c.clause_number for c in op.new_clauses] == ["68C", "68D"]
    # bodies pulled from source, not from the model
    texts = {c.clause_number: c.text for c in op.new_clauses}
    assert "shall not be recognised as income" in texts["68C"]
    assert "non-interest / other income" in texts["68D"]
    assert texts["68C"] in _norm(rrb_section) and texts["68D"] in _norm(rrb_section)


def test_hallucinated_clause_number_downgrades(rrb_section):
    # model claims a clause that isn't in the source -> unresolved
    res = postprocess(
        _model_json("The following shall be inserted in Chapter V", clauses=("68C", "999Z")),
        rrb_section,
    )
    op = res.operations[0]
    assert op.operation == "unresolved"
    assert "999Z" in (op.note or "")


# --- fence stripping ---
def test_fence_stripping(rrb_section):
    raw = "```json\n" + _model_json("The following shall be inserted in Chapter V") + "\n```"
    assert postprocess(raw, rrb_section).operations[0].operation == "insert"


def test_strip_fences_extracts_object():
    assert strip_fences('```json\n{"a":1}\n```') == '{"a":1}'
    assert strip_fences('prose before {"a":1} prose after') == '{"a":1}'


# --- the hallucination guard ---
def test_evidence_not_verbatim_downgrades_to_unresolved(rrb_section):
    res = postprocess(_model_json("This sentence is fabricated and absent from source"), rrb_section)
    op = res.operations[0]
    assert op.operation == "unresolved"
    assert "evidence_span" in (op.note or "")


def test_whitespace_differences_still_match(rrb_section):
    # A verbatim span with collapsed/expanded whitespace must still validate.
    res = postprocess(_model_json("The   following  shall be inserted in Chapter V"), rrb_section)
    assert res.operations[0].operation == "insert"


# --- confidence gating ---
def test_low_confidence_downgrades(rrb_section):
    res = postprocess(_model_json("The following shall be inserted in Chapter V", 0.3), rrb_section)
    assert res.operations[0].operation == "unresolved"


# --- unresolved is a first-class output ---
def test_unresolved_passthrough(rrb_section):
    raw = json.dumps(
        {"operations": [{"seq": 1, "operation": "unresolved", "evidence_span": "", "confidence": 0.2}]}
    )
    assert postprocess(raw, rrb_section).operations[0].operation == "unresolved"


def test_invalid_json_raises(rrb_section):
    with pytest.raises(ParseError):
        postprocess("not json at all", rrb_section)


# --- live smoke (skips unless the configured parse model is pulled) ---
def _ollama_models() -> set[str]:
    try:
        r = httpx.get(f"{config.ollama_host}/api/tags", timeout=3)
        return {m["name"] for m in r.json().get("models", [])}
    except Exception:
        return set()


def test_live_parse_if_model_available(rrb_section):
    if config.ollama_model_parse not in _ollama_models():
        pytest.skip(f"{config.ollama_model_parse} not pulled")
    from rbi.parse.runner import parse_document

    for p in sorted(SAMPLES_DIR.glob("*.pdf")):
        t = normalise(extract_pdf(p))
        if "RBI/2026-27/201" in t:
            result = parse_document(t)
            assert result.operations, "model returned no operations"
            break
