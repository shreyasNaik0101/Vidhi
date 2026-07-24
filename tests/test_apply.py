"""Apply stage — timeline building, the overlap invariant, and the as-of resolver.

Fully deterministic: operations are hand-built (no model), so this exercises the
date-flip demo (Definition of Done #1) and the abstention paths directly.
"""
from __future__ import annotations

from datetime import date

import pytest

from rbi.apply.build import assert_no_overlap, build_timeline, make_sort_key
from rbi.apply.models import ClauseVersion
from rbi.apply.resolve import resolve
from rbi.classify.rules import DocumentMeta
from rbi.parse.schema import NewClause, Operation

EFF = date(2026, 10, 1)


def _meta(ref: str, entity: str) -> DocumentMeta:
    return DocumentMeta(
        rbi_ref=ref, title=f"{entity} IRACP", doc_type="amendment", md_family="IRACP",
        entity_type_code=entity, issued_date=date(2026, 7, 16), effective_date=EFF,
    )


def _insert(seq: int, chapter: str, clauses: dict[str, str]) -> Operation:
    return Operation(
        seq=seq, operation="insert", target_chapter=chapter,
        clause_numbers=list(clauses),
        new_clauses=[NewClause(clause_number=n, text=t) for n, t in clauses.items()],
        evidence_span="x", confidence=1.0,
    )


@pytest.fixture
def rrb_lab_timeline():
    entries = [
        (_meta("RBI/2026-27/201", "RRB"),
         [_insert(1, "V", {"68C": "RRB accrued interest text", "68D": "RRB income text"})]),
        (_meta("RBI/2026-27/202", "LAB"),
         [_insert(1, "V", {"119C": "LAB accrued interest text", "119D": "LAB income text"})]),
    ]
    return build_timeline(entries)


# --- sort key ---
def test_sort_key_orders_within_chapter():
    assert make_sort_key("68C") == "00068C"
    assert make_sort_key("119D") == "00119D"
    assert make_sort_key("9") < make_sort_key("68C") < make_sort_key("119C")


# --- building ---
def test_insert_creates_open_versions(rrb_lab_timeline):
    assert len(rrb_lab_timeline) == 4
    for v in rrb_lab_timeline:
        assert v.valid_from == EFF and v.valid_to is None
    assert_no_overlap(rrb_lab_timeline)


# --- THE DATE FLIP (Definition of Done #1) ---
def test_date_flip_before_effective_is_not_yet_in_force(rrb_lab_timeline):
    r = resolve(rrb_lab_timeline, md_family="IRACP", entity_type_code="RRB",
                clause_number="68C", as_of=date(2026, 9, 30))
    assert r.status == "not_yet_in_force"
    assert r.effective_date == EFF
    assert r.text is None
    assert r.candidates  # abstention is transparent — it shows what it considered


def test_date_flip_after_effective_is_in_force(rrb_lab_timeline):
    r = resolve(rrb_lab_timeline, md_family="IRACP", entity_type_code="RRB",
                clause_number="68C", as_of=date(2026, 10, 2))
    assert r.status == "in_force"
    assert r.text == "RRB accrued interest text"
    assert r.valid_from == EFF


def test_effective_day_itself_is_in_force(rrb_lab_timeline):
    r = resolve(rrb_lab_timeline, md_family="IRACP", entity_type_code="RRB",
                clause_number="68C", as_of=EFF)
    assert r.status == "in_force"


# --- entity trap (category 3) ---
def test_lab_clause_number_asked_of_rrb_abstains(rrb_lab_timeline):
    r = resolve(rrb_lab_timeline, md_family="IRACP", entity_type_code="RRB",
                clause_number="119C", as_of=date(2026, 10, 2))
    assert r.status == "no_provision"
    assert r.text is None


def test_same_number_resolves_per_entity(rrb_lab_timeline):
    r = resolve(rrb_lab_timeline, md_family="IRACP", entity_type_code="LAB",
                clause_number="119C", as_of=date(2026, 10, 2))
    assert r.status == "in_force"
    assert r.text == "LAB accrued interest text"


# --- substitute closes the prior version (the timeline machinery) ---
def test_substitute_supersedes_prior_version():
    orig = _meta("RBI/2026-27/201", "RRB")
    later = _meta("RBI/2027-28/050", "RRB")
    later.effective_date = date(2027, 1, 1)
    sub = Operation(
        seq=1, operation="substitute", target_chapter="V", clause_numbers=["68C"],
        new_clauses=[NewClause(clause_number="68C", text="revised 68C text")],
        evidence_span="x", confidence=1.0,
    )
    versions = build_timeline([
        (orig, [_insert(1, "V", {"68C": "original 68C text"})]),
        (later, [sub]),
    ])
    assert_no_overlap(versions)

    before = resolve(versions, md_family="IRACP", entity_type_code="RRB",
                     clause_number="68C", as_of=date(2026, 12, 1))
    after = resolve(versions, md_family="IRACP", entity_type_code="RRB",
                    clause_number="68C", as_of=date(2027, 2, 1))
    assert before.text == "original 68C text"
    assert after.text == "revised 68C text"


# --- omit closes the version, adds nothing ---
def test_omit_closes_version():
    orig = _meta("RBI/2026-27/201", "RRB")
    later = _meta("RBI/2027-28/060", "RRB")
    later.effective_date = date(2027, 1, 1)
    omit = Operation(seq=1, operation="omit", clause_numbers=["68C"],
                     evidence_span="x", confidence=1.0)
    versions = build_timeline([
        (orig, [_insert(1, "V", {"68C": "original 68C text"})]),
        (later, [omit]),
    ])
    r = resolve(versions, md_family="IRACP", entity_type_code="RRB",
                clause_number="68C", as_of=date(2027, 2, 1))
    assert r.status == "no_longer_in_force"


# --- the overlap invariant fails loudly ---
def test_overlap_assertion_catches_conflict():
    bad = [
        ClauseVersion("IRACP", "RRB", "68C", "00068C", "V", "a", date(2026, 10, 1), None),
        ClauseVersion("IRACP", "RRB", "68C", "00068C", "V", "b", date(2027, 1, 1), None),
    ]
    with pytest.raises(AssertionError):
        assert_no_overlap(bad)
