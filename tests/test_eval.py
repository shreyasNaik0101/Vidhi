"""Eval harness — scoring logic and Baseline C on a hand-built system (no model)."""
from __future__ import annotations

from datetime import date

from rbi.apply.build import build_timeline
from rbi.classify.rules import DocumentMeta
from rbi.eval.golden import GoldenQuestion, load_golden
from rbi.eval.metrics import Prediction, is_correct, score
from rbi.eval.system import FullSystem
from rbi.group.build import group_ops
from rbi.group.models import OpRef
from rbi.parse.schema import NewClause, Operation

_68C = ("Any accrued but unrealised interest and / or charges from the extinguished exposure "
        "pertaining to periods prior to acquisition of a Specified Non-Financial Asset (SNFA), "
        "shall not be recognised as income upon acquisition of the SNFA.")
_68D = ("Any income received from an SNFA shall be recognised in the income statement as "
        "'non-interest / other income', in the financial year in which it is realised.")
_119C = _68C.replace("a Specified Non-Financial Asset (SNFA),", "an SNFA,")

EFF = date(2026, 10, 1)


def _build_rrb_lab_system() -> FullSystem:
    spec = {"RRB": {"68C": _68C, "68D": _68D}, "LAB": {"119C": _119C, "119D": _68D}}
    entries, ops = [], []
    for entity, clauses in spec.items():
        meta = DocumentMeta(
            rbi_ref=f"RBI/2026-27/{'201' if entity == 'RRB' else '202'}",
            title=f"{entity} IRACP", doc_type="amendment", md_family="IRACP",
            entity_type_code=entity, issued_date=date(2026, 7, 16), effective_date=EFF,
        )
        op = Operation(
            seq=1, operation="insert", target_chapter="V", clause_numbers=list(clauses),
            new_clauses=[NewClause(clause_number=n, text=t) for n, t in clauses.items()],
            evidence_span="x", confidence=1.0,
        )
        entries.append((meta, [op]))
        ops.append(OpRef(op_ref=f"{meta.rbi_ref}#seq1", entity_type_code=entity,
                         md_family="IRACP", issued_date=date(2026, 7, 16), effective_date=EFF,
                         text=" ".join(clauses.values()), clause_numbers=list(clauses)))
    return FullSystem(build_timeline(entries), group_ops(ops))


# --- scoring unit checks ---
def test_lookup_correct_requires_in_force_and_substring():
    q = GoldenQuestion(id="x", category="lookup", question="?", entity_type="RRB",
                       clause="68C", as_of=EFF, expected_status="in_force",
                       expected_contains="non-interest")
    assert not is_correct(q, Prediction(status="in_force", text="something else"))
    assert is_correct(q, Prediction(status="in_force", text="... non-interest ..."))


def test_temporal_and_entity_correctness():
    tq = GoldenQuestion(id="t", category="temporal_trap", question="?", expected_status="not_yet_in_force")
    assert is_correct(tq, Prediction(status="not_yet_in_force"))
    assert not is_correct(tq, Prediction(status="in_force", text="x"))
    eq = GoldenQuestion(id="e", category="entity_trap", question="?", expected_status="no_provision")
    assert is_correct(eq, Prediction(status="no_provision"))


# --- Baseline C behaviour on the RRB/LAB corpus ---
def test_full_system_answers_rrb_lookup():
    sys = _build_rrb_lab_system()
    q = GoldenQuestion(id="g001", category="lookup", question="?", entity_type="RRB",
                       clause="68C", as_of=date(2026, 10, 15), expected_status="in_force")
    assert sys.answer(q).status == "in_force"


def test_full_system_date_flip():
    sys = _build_rrb_lab_system()
    before = GoldenQuestion(id="a", category="temporal_trap", question="?", entity_type="RRB",
                            clause="68C", as_of=date(2026, 9, 30), expected_status="not_yet_in_force")
    after = GoldenQuestion(id="b", category="lookup", question="?", entity_type="RRB",
                           clause="68C", as_of=date(2026, 10, 2), expected_status="in_force")
    assert sys.answer(before).status == "not_yet_in_force"
    assert sys.answer(after).status == "in_force"


def test_full_system_cross_entity_equivalence():
    sys = _build_rrb_lab_system()
    q = GoldenQuestion(id="g025", category="cross_entity", question="?", entity_type="RRB",
                       reference_entity="LAB", reference_clause="119C",
                       expected_status="equivalence", expected_clause="68C")
    assert sys.answer(q).clause == "68C"


def test_full_system_abstains_on_uningested_entity():
    sys = _build_rrb_lab_system()
    q = GoldenQuestion(id="g005", category="lookup", question="?", entity_type="SFB",
                       clause="133C", as_of=date(2026, 12, 1), expected_status="in_force")
    # honest coverage gap: SFB not ingested -> abstain, not a wrong answer
    assert sys.answer(q).status == "no_provision"


# --- end-to-end scoring never produces entity/temporal errors ---
def test_no_entity_or_temporal_errors_on_full_golden():
    sys = _build_rrb_lab_system()
    report = score("C", load_golden(), sys.answer)
    assert report.entity_error_rate == 0.0
    assert report.temporal_error_rate == 0.0
    # resolver-backed categories should be fully correct on the RRB/LAB corpus
    by_cat = report.by_category()
    assert by_cat["entity_trap"][0] == by_cat["entity_trap"][1]
    assert by_cat["non_existent"][0] == by_cat["non_existent"][1]
