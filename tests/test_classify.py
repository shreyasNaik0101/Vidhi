"""Classify stage — exact expected metadata for both sample docs (CLAUDE.md §6.3)."""
from __future__ import annotations

import re
from datetime import date

import pytest

from rbi.classify.rules import classify_text
from rbi.config import SAMPLES_DIR
from rbi.extract.normalise import normalise
from rbi.extract.pdf import extract_pdf


@pytest.fixture(scope="module")
def metas():
    out = {}
    for p in sorted(SAMPLES_DIR.glob("*.pdf")):
        text = normalise(extract_pdf(p))
        ref = re.search(r"RBI/\d{4}-\d{2}/\d+", text).group(0)
        out[ref] = classify_text(text)
    return out


def test_both_classified_by_regex_alone(metas):
    for meta in metas.values():
        assert meta.missing == [], f"regex missed fields: {meta.missing}"
        assert meta.method == "regex"


def test_rrb_fields(metas):
    m = metas["RBI/2026-27/201"]
    assert m.dor_ref == "DOR.STR.REC.166/21-04-048/2026-27"
    assert m.entity_type_code == "RRB"
    assert m.md_family == "IRACP"
    assert m.doc_type == "amendment"
    assert m.issued_date == date(2026, 7, 16)
    assert m.effective_date == date(2026, 10, 1)


def test_lab_fields(metas):
    m = metas["RBI/2026-27/202"]
    assert m.dor_ref == "DOR.STR.REC.167/21-04-048/2026-27"
    assert m.entity_type_code == "LAB"
    assert m.md_family == "IRACP"
    assert m.effective_date == date(2026, 10, 1)


def test_issued_before_effective(metas):
    # The property the whole demo turns on: published != in force.
    for m in metas.values():
        assert m.issued_date < m.effective_date


def test_md_family_from_title_not_parent_reference():
    # Title is IRACP even though the body references the RSA parent amendment first
    # in the same line. md_family must come from the title, not first-match.
    text = (
        "RBI/2026-27/201 July 16, 2026 "
        "Reserve Bank of India (Regional Rural Banks – Income Recognition, Asset "
        "Classification and Provisioning) Second Amendment Directions, 2026 "
        "Please refer to Reserve Bank of India (Regional Rural Banks – Resolution of "
        "Stressed Assets) Second Amendment Directions, 2026 dated July 16, 2026."
    )
    assert classify_text(text).md_family == "IRACP"


def test_entity_name_variants_map_to_codes():
    # 'Urban Cooperative Banks' (no hyphen) and 'Co-operative' both resolve.
    t = ("RBI/2026-27/999 July 16, 2026 Reserve Bank of India (Urban Cooperative Banks "
         "– Income Recognition, Asset Classification and Provisioning) Second Amendment "
         "Directions, 2026")
    assert classify_text(t).entity_type_code == "UCB"
