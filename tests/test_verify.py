"""Verify stage — routing, the deterministic stub verifier, and reject -> unresolved."""
from __future__ import annotations

from rbi.parse.schema import NewClause, Operation
from rbi.verify.router import needs_verify
from rbi.verify.verifier import StubVerifier, verify_operations

SRC = "The following shall be inserted in Chapter V. 68C. Any accrued interest on an SNFA."


def _op(conf, operation="insert", clauses=("68C",), evidence="shall be inserted in Chapter V"):
    return Operation(seq=1, operation=operation, target_chapter="V", clause_numbers=list(clauses),
                     new_clauses=[NewClause(clause_number=c, text="...") for c in clauses],
                     evidence_span=evidence, confidence=conf)


# --- routing: only the uncertain middle band, plus a calibration sample ---
def test_router_verifies_uncertain_band():
    assert needs_verify(_op(0.7)) is True


def test_router_skips_low_and_unresolved():
    assert needs_verify(_op(0.4)) is False                       # < 0.5 downgraded upstream
    assert needs_verify(_op(0.0, operation="unresolved")) is False


def test_router_samples_confident_ones():
    assert needs_verify(_op(0.95), sample_rate=1.0) is True      # always sample
    assert needs_verify(_op(0.95), sample_rate=0.0) is False     # never sample


# --- the stub verifier ---
def test_stub_confirms_a_valid_parse():
    assert StubVerifier().verify(_op(0.7), SRC).verdict == "confirm"


def test_stub_rejects_fabricated_evidence():
    r = StubVerifier().verify(_op(0.7, evidence="this sentence is not in the source"), SRC)
    assert r.verdict == "reject" and "evidence" in r.notes


def test_stub_rejects_missing_clause():
    r = StubVerifier().verify(_op(0.7, clauses=("999Z",)), SRC)
    assert r.verdict == "reject"


# --- the stage: rejected ops are downgraded, confident/unresolved are skipped ---
def test_verify_downgrades_rejected_to_unresolved():
    ops = [_op(0.7, evidence="not present in the source at all")]
    results = verify_operations(ops, SRC)
    assert results[0].verdict == "reject"
    assert ops[0].operation == "unresolved"
    assert "rejected" in (ops[0].note or "")


def test_verify_skips_confident_and_unresolved():
    ops = [_op(0.95), _op(0.0, operation="unresolved")]
    assert verify_operations(ops, SRC, sample_rate=0.0) == []
