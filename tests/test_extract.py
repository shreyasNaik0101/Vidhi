"""One test per documented extraction quirk (PROJECT_SPEC.md §6.2), against the two sample PDFs."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from rbi.config import SAMPLES_DIR
from rbi.extract.normalise import nfkc, normalise
from rbi.extract.pdf import extract_pdf

# Map the (hash-named) sample files to the entity they belong to.
SAMPLES = sorted(SAMPLES_DIR.glob("*.pdf"))
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


@pytest.fixture(scope="module")
def texts() -> dict[str, str]:
    """rbi_ref -> normalised text, keyed by the ref found in each PDF."""
    out: dict[str, str] = {}
    for p in SAMPLES:
        clean = normalise(extract_pdf(p))
        m = re.search(r"RBI/\d{4}-\d{2}/\d+", clean)
        assert m, f"no RBI ref found in {p.name}"
        out[m.group(0)] = clean
    return out


def test_two_samples_present():
    assert len(SAMPLES) == 2, "expected the two verified sample PDFs in data/samples/"


def test_both_refs_parse(texts):
    assert set(texts) == {"RBI/2026-27/201", "RBI/2026-27/202"}


# --- Quirk 3: ligatures ---
def test_nfkc_collapses_ffi_ligature():
    assert nfkc("Central Oﬃce") == "Central Office"


def test_no_ligature_codepoints_survive(texts):
    for clean in texts.values():
        assert "ﬃ" not in clean and "ﬁ" not in clean  # ﬃ, ﬁ


# --- Quirk 2: Devanagari mojibake dropped ---
def test_no_devanagari_heavy_lines(texts):
    for clean in texts.values():
        for line in clean.splitlines():
            stripped = re.sub(r"\s", "", line)
            if stripped:
                share = len(DEVANAGARI.findall(stripped)) / len(stripped)
                assert share <= 0.30, f"devanagari line survived: {line!r}"


# --- Quirk 1: address boilerplate stripped ---
def test_boilerplate_removed(texts):
    for clean in texts.values():
        assert "www.rbi.org.in" not in clean
        assert "Shahid Bhagat Singh Marg" not in clean
        assert "Department of Regulation" not in clean


# --- Quirk 4: orphaned footnote marker dropped (Doc B emits a bare '2') ---
def test_orphan_footnote_marker_dropped(texts):
    clean = texts["RBI/2026-27/202"]
    assert not any(line.strip() == "2" for line in clean.splitlines())


# --- Quirk 5: hard wraps reflowed — clause 68C is one line, not several ---
def test_clause_reflowed_into_one_line(texts):
    clean = texts["RBI/2026-27/201"]
    lines = clause_lines(clean, "68C")
    assert len(lines) == 1, f"68C spread across {len(lines)} lines"
    assert "shall not be recognised as income" in lines[0]


def test_effective_date_present(texts):
    for clean in texts.values():
        assert "October 01, 2026" in clean


def test_rrb_lab_wording_difference_preserved(texts):
    # The single substantive difference the verifier agent exists for (PROJECT_SPEC.md §2).
    assert "a Specified Non-Financial Asset (SNFA)," in texts["RBI/2026-27/201"]
    assert "an SNFA," in texts["RBI/2026-27/202"]


def clause_lines(clean: str, number: str) -> list[str]:
    return [ln for ln in clean.splitlines() if re.match(rf"^[“\"]?{re.escape(number)}\.", ln)]
