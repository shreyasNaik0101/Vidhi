"""Normalisation of extracted PDF text (PROJECT_SPEC.md §6.2).

Five verified quirks in the sample PDFs, each handled here and covered by a test:

  1. Header/footer boilerplate extracts before the body — strip the Mumbai address block.
  2. Devanagari is mojibake (broken font encoding) — drop lines that are >30% Devanagari.
  3. Ligatures — NFKC-normalise every string so 'Oﬃce' -> 'Office'.
  4. Orphaned footnote markers — drop lines that are a bare number.
  5. Hard line wraps mid-sentence — reflow, breaking only on structural starts.

Note: real RBI text contains typos ('in, in exercise', 'modifies'). We do NOT fix
those — downstream matching must tolerate them (PROJECT_SPEC.md §13).
"""
from __future__ import annotations

import re
import unicodedata

# --- 2. Devanagari mojibake ---
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_DEVANAGARI_MAX_SHARE = 0.30

# --- 1. Boilerplate address block (English lines the Devanagari filter won't catch) ---
_BOILERPLATE = re.compile(
    r"(www\.rbi\.org\.in"
    r"|_{3,}.*RESERVE BANK OF INDIA"
    r"|Department of Regulation"
    r"|Central Office Building"
    r"|Shahid Bhagat Singh Marg"
    r"|Tel\s*No"
    r"|Fax\s*No"
    r"|टेल|फैक्स)",  # devanagari 'Tel'/'Fax' labels sharing a mixed line
    re.IGNORECASE,
)

# --- 4. Orphaned footnote marker: a line that is nothing but a number ---
_BARE_NUMBER = re.compile(r"^\d{1,3}$")

# --- 5. Structural line starts that must begin a new (un-joined) logical line ---
_NEW_BLOCK = re.compile(
    r"^\s*[“\"]?("
    r"\d+[A-Z]?\."       # clause: 68C.  68D.  4.  (also numbered para)
    r"|\([ivxlc]+\)"     # roman sub-item: (i) (ii)
    r"|\([a-z]\)"        # lettered sub-item: (a) (b)
    r"|[A-Z]\d*\.\s"     # section heading: 'B. '  'E1. '
    r")"
)


def nfkc(text: str) -> str:
    """Quirk 3: collapse ligatures and compatibility glyphs."""
    return unicodedata.normalize("NFKC", text)


def _devanagari_share(line: str) -> float:
    stripped = re.sub(r"\s", "", line)
    if not stripped:
        return 0.0
    return len(_DEVANAGARI.findall(stripped)) / len(stripped)


def _is_boilerplate(line: str) -> bool:
    return bool(_BOILERPLATE.search(line))


def _starts_new_block(line: str) -> bool:
    return bool(_NEW_BLOCK.match(line))


def _keep(line: str) -> bool:
    """Line-level filters: quirks 1, 2, 4."""
    s = line.strip()
    if not s:
        return False
    if not re.search(r"\w", s):          # punctuation/combining-mark noise only
        return False
    if _BARE_NUMBER.match(s):            # 4. orphaned footnote marker
        return False
    if _devanagari_share(s) > _DEVANAGARI_MAX_SHARE:  # 2. mojibake
        return False
    if _is_boilerplate(s):              # 1. address boilerplate
        return False
    return True


def _reflow(lines: list[str]) -> list[str]:
    """Quirk 5: join hard-wrapped continuation lines back into their sentence."""
    out: list[str] = []
    for raw in lines:
        line = raw.strip()
        if out and not _starts_new_block(line):
            out[-1] = f"{out[-1]} {line}"
        else:
            out.append(line)
    return out


def normalise(raw_text: str) -> str:
    """Full pipeline: NFKC -> line filters -> reflow. Returns cleaned body text."""
    text = nfkc(raw_text)
    kept = [ln for ln in text.splitlines() if _keep(ln)]
    reflowed = _reflow(kept)
    return "\n".join(reflowed)
