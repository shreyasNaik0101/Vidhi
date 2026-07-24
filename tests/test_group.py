"""Group stage — similarity, clustering, and the cross-entity fan-out (§6.7).

Deterministic (word-level similarity, no model). A live embedding test skips when
the embedding model is absent.
"""
from __future__ import annotations

from datetime import date

import httpx
import pytest

from rbi.config import SAMPLES_DIR, config
from rbi.extract.normalise import normalise
from rbi.extract.pdf import extract_pdf
from rbi.group.build import group_ops
from rbi.group.models import OpRef
from rbi.group.similarity import cosine, word_similarity
from rbi.parse.clauses import extract_clause_text
from rbi.parse.section import operative_section

ISSUED = date(2026, 7, 16)
EFFECTIVE = date(2026, 10, 1)

# Full clause text; the ONLY difference is 'a Specified Non-Financial Asset (SNFA),'
# vs 'an SNFA,' — the documented 0.957-similarity pair (CLAUDE.md §2).
_COMMON_TAIL = (
    " shall not be recognised as income upon acquisition of the SNFA. Where such income "
    "has been recognised in respect of any SNFA outstanding in the books of a bank as on "
    "September 30, 2026, it shall be reversed through Profit and Loss account, latest by "
    "September 30, 2027, to the extent remaining unrealised as on that date."
)
_HEAD = ("Any accrued but unrealised interest and / or charges from the extinguished exposure "
         "pertaining to periods prior to acquisition of ")
RRB_68C = _HEAD + "a Specified Non-Financial Asset (SNFA)," + _COMMON_TAIL
LAB_119C = _HEAD + "an SNFA," + _COMMON_TAIL


def _op(ref, entity, text, clauses, issued=ISSUED):
    return OpRef(op_ref=ref, entity_type_code=entity, md_family="IRACP",
                 issued_date=issued, effective_date=EFFECTIVE, text=text,
                 clause_numbers=clauses)


# --- similarity ---
def test_near_identical_scores_high():
    assert word_similarity(RRB_68C, LAB_119C) > 0.9


def test_different_text_scores_low():
    assert word_similarity(RRB_68C, "Banks shall maintain a capital adequacy ratio.") < 0.5


def test_cosine_basic():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)


# --- the fan-out: same change, different clause numbers, one group ---
def test_rrb_lab_group_together():
    ops = [
        _op("RBI/2026-27/201#seq1", "RRB", RRB_68C, ["68C"]),
        _op("RBI/2026-27/202#seq1", "LAB", LAB_119C, ["119C"]),
    ]
    groups = group_ops(ops)
    assert len(groups) == 1
    g = groups[0]
    assert g.entity_codes == ["LAB", "RRB"]
    assert g.label == "SNFA income recognition"
    assert g.effective_date == EFFECTIVE
    assert all(m.similarity > 0.9 for m in g.members)


def test_three_entity_fanout():
    sfb = LAB_119C  # SFB carries the same 'an SNFA,' wording at clause 133C
    ops = [
        _op("a#1", "RRB", RRB_68C, ["68C"]),
        _op("b#1", "LAB", LAB_119C, ["119C"]),
        _op("c#1", "SFB", sfb, ["133C"]),
    ]
    groups = group_ops(ops)
    assert len(groups) == 1
    assert set(groups[0].entity_codes) == {"RRB", "LAB", "SFB"}


def test_different_issued_dates_do_not_group():
    ops = [
        _op("a#1", "RRB", RRB_68C, ["68C"], issued=date(2026, 7, 16)),
        _op("b#1", "LAB", LAB_119C, ["119C"], issued=date(2026, 8, 20)),
    ]
    assert group_ops(ops) == []  # different buckets, each a singleton


def test_dissimilar_same_date_do_not_group():
    ops = [
        _op("a#1", "RRB", RRB_68C, ["68C"]),
        _op("b#1", "LAB", "An entirely unrelated provision about liquidity ratios.", ["120A"]),
    ]
    assert group_ops(ops) == []


def test_singletons_flag_returns_lone_ops():
    ops = [_op("a#1", "RRB", RRB_68C, ["68C"])]
    assert group_ops(ops, singletons=True)


# --- reference value against the real extracted clause texts ---
def test_reference_similarity_on_real_samples():
    texts = {}
    for p in sorted(SAMPLES_DIR.glob("*.pdf")):
        t = normalise(extract_pdf(p))
        s = operative_section(t)
        if "RBI/2026-27/201" in t:
            texts["RRB"] = extract_clause_text(s, "68C")
        if "RBI/2026-27/202" in t:
            texts["LAB"] = extract_clause_text(s, "119C")
    sim = word_similarity(texts["RRB"], texts["LAB"])
    assert 0.94 <= sim <= 0.98  # ~0.957 reference


# --- live embeddings (skips unless the embed model is pulled) ---
def _ollama_models() -> set[str]:
    try:
        r = httpx.get(f"{config.ollama_host}/api/tags", timeout=3)
        return {m["name"] for m in r.json().get("models", [])}
    except Exception:
        return set()


def test_live_embedding_grouping_if_available():
    from rbi.group.embed import DEFAULT_EMBED_MODEL, embedding_similarity_fn

    if DEFAULT_EMBED_MODEL not in _ollama_models():
        pytest.skip(f"{DEFAULT_EMBED_MODEL} not pulled")
    ops = [
        _op("RBI/2026-27/201#seq1", "RRB", RRB_68C, ["68C"]),
        _op("RBI/2026-27/202#seq1", "LAB", LAB_119C, ["119C"]),
    ]
    groups = group_ops(ops, threshold=0.85, similarity_fn=embedding_similarity_fn(ops))
    assert len(groups) == 1
    assert set(groups[0].entity_codes) == {"RRB", "LAB"}
