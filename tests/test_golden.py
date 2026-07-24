"""Validate the golden set structure and cross-check its labels against the resolver."""
from __future__ import annotations

from collections import Counter
from datetime import date

import pytest

from rbi.apply.build import build_timeline
from rbi.apply.resolve import resolve
from rbi.classify.rules import DocumentMeta
from rbi.eval.golden import VALID_ENTITY_CODES, load_golden
from rbi.parse.schema import NewClause, Operation

GOLDEN = load_golden()
CATEGORIES = {"lookup", "temporal_trap", "entity_trap", "cross_entity", "non_existent", "cascade"}

# Real clause bodies (verbatim from the samples / recon) so expected_contains matches.
_68C = ("Any accrued but unrealised interest and / or charges from the extinguished exposure "
        "pertaining to periods prior to acquisition of a Specified Non-Financial Asset (SNFA), "
        "shall not be recognised as income upon acquisition of the SNFA. Where such income has "
        "been recognised in respect of any SNFA outstanding in the books of a bank as on "
        "September 30, 2026, it shall be reversed through Profit and Loss account, latest by "
        "September 30, 2027, to the extent remaining unrealised as on that date.")
_68D = ("Any income received from an SNFA shall be recognised in the income statement as "
        "'non-interest / other income', in the financial year in which it is realised. Similarly, "
        "any expense incurred towards upkeep of an SNFA shall be accounted for in the income "
        "statement in the financial year in which it is incurred.")
_119C = _68C.replace("a Specified Non-Financial Asset (SNFA),", "an SNFA,")

# (entity, {clause: text}) — the three entities the golden set references by clause.
_TIMELINE_SPEC = {
    "RRB": {"68C": _68C, "68D": _68D},
    "LAB": {"119C": _119C, "119D": _68D},
    "SFB": {"133C": _119C, "133D": _68D},
}


@pytest.fixture(scope="module")
def timeline():
    entries = []
    for entity, clauses in _TIMELINE_SPEC.items():
        meta = DocumentMeta(
            rbi_ref=f"REF/{entity}", title=f"{entity} IRACP", doc_type="amendment",
            md_family="IRACP", entity_type_code=entity,
            issued_date=date(2026, 7, 16), effective_date=date(2026, 10, 1),
        )
        op = Operation(
            seq=1, operation="insert", target_chapter="V",
            clause_numbers=list(clauses),
            new_clauses=[NewClause(clause_number=n, text=t) for n, t in clauses.items()],
            evidence_span="x", confidence=1.0,
        )
        entries.append((meta, [op]))
    return build_timeline(entries)


# --- structure ---
def test_at_least_40_questions():
    assert len(GOLDEN) >= 40


def test_ids_unique():
    ids = [q.id for q in GOLDEN]
    assert len(ids) == len(set(ids))


def test_all_categories_present_and_balanced():
    counts = Counter(q.category for q in GOLDEN)
    assert set(counts) == CATEGORIES
    assert min(counts.values()) >= 6, f"thin category: {counts}"


def test_entity_codes_valid():
    for q in GOLDEN:
        if q.entity_type:
            assert q.entity_type in VALID_ENTITY_CODES, q.id
        for e in q.expected_entities:
            assert e in VALID_ENTITY_CODES, q.id


def test_status_matches_category():
    allowed = {
        "lookup": {"in_force"},
        "temporal_trap": {"not_yet_in_force"},
        "entity_trap": {"no_provision"},
        "non_existent": {"no_provision"},
        "cross_entity": {"equivalence"},
        "cascade": {"cascade"},
    }
    for q in GOLDEN:
        assert q.expected_status in allowed[q.category], q.id


def test_cross_entity_has_reference_and_target():
    for q in GOLDEN:
        if q.category == "cross_entity":
            assert q.reference_entity and q.reference_clause and q.expected_clause, q.id


# --- the strong check: golden labels agree with the resolver ---
@pytest.mark.parametrize(
    "q", [q for q in GOLDEN if q.category in
          {"lookup", "temporal_trap", "entity_trap", "non_existent"}],
    ids=lambda q: q.id,
)
def test_resolver_agrees_with_golden(timeline, q):
    r = resolve(
        timeline, md_family=q.md_family, entity_type_code=q.entity_type,
        clause_number=q.clause, as_of=q.as_of,
    )
    assert r.status == q.expected_status, f"{q.id}: resolver said {r.status}"
    if q.expected_contains and r.status == "in_force":
        assert q.expected_contains in r.text, q.id
