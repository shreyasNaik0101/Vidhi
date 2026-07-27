"""Regex-first document classification (CLAUDE.md §6.3).

Extracts the fields of a `document` row from normalised text. Regex handles the
sample docs entirely; `missing` lists any required field a regex could not fill,
which is the trigger for the gemma3:4b fallback (not needed for the samples).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

# --- reference numbers ---
_RBI_REF = re.compile(r"RBI/\d{4}-\d{2}/\d+")
_DOR_REF = re.compile(r"DOR\.[A-Z]{3}\.[A-Z]{3}\.\d+/[\d-]+/\d{4}-\d{2}")

# --- title: 'Reserve Bank of India (<entity> – <subject>) <...> Directions, YYYY' ---
_TITLE = re.compile(
    r"Reserve Bank of India\s*\([^)]+\)[^\n]*?Directions,\s*20\d{2}"
)
_PARENTHETICAL = re.compile(r"Reserve Bank of India\s*\(([^)]+)\)")

# --- dates ---
# An explicit effective date after any of the common "in force" phrasings. The date
# itself must be proper-case (parsed with %B); only the phrase is case-insensitive.
_EFFECTIVE = re.compile(
    r"(?:[Cc]ome into force|[Cc]omes into force|[Ss]hall come into force|"
    r"[Ee]ffective|[Ww]ith effect|[Ww]\.e\.f\.?)"
    r"[^.\n]{0,40}?"
    r"([A-Z][a-z]+ \d{1,2}, \d{4})"
)
# "with immediate effect" / "at once" -> effective = the issue date.
_IMMEDIATE = re.compile(
    r"with immediate effect|come into force at once|effective immediately",
    re.IGNORECASE,
)
_ANY_DATE = re.compile(r"[A-Z][a-z]+ \d{1,2}, \d{4}")

# entity display name (normalised) -> code, matching seed.sql
_ENTITY_CODES = {
    "local area banks": "LAB",
    "regional rural banks": "RRB",
    "rural cooperative banks": "RCB",
    "urban cooperative banks": "UCB",
    "all india financial institutions": "AIFI",
    "non banking financial companies": "NBFC",
    "small finance banks": "SFB",
    "commercial banks": "SCB",
    "payments banks": "PB",
    "housing finance companies": "HFC",
    "asset reconstruction companies": "ARC",
}


@dataclass
class DocumentMeta:
    rbi_ref: str | None = None
    dor_ref: str | None = None
    title: str | None = None
    doc_type: str | None = None          # 'amendment' | 'master_direction'
    md_family: str | None = None         # 'IRACP' | 'RSA' | ...
    entity_type_code: str | None = None  # 'RRB', 'LAB', ...
    issued_date: date | None = None
    effective_date: date | None = None   # None => same as issued_date
    method: str = "regex"
    missing: list[str] = field(default_factory=list)


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%B %d, %Y").date()


def _norm_entity(raw: str) -> str:
    # take the segment before the dash, normalise 'co-operative' etc.
    name = re.split(r"[–-]", raw, maxsplit=1)[0]
    name = name.lower().replace("-", " ")
    name = re.sub(r"[^a-z ]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def _md_family(title: str) -> str | None:
    t = title.lower()
    if "income recognition" in t and "asset classification" in t:
        return "IRACP"
    if "resolution of stressed assets" in t:
        return "RSA"
    return None


def classify_text(text: str) -> DocumentMeta:
    m = DocumentMeta()

    if r := _RBI_REF.search(text):
        m.rbi_ref = r.group(0)
    if d := _DOR_REF.search(text):
        m.dor_ref = d.group(0)

    if t := _TITLE.search(text):
        m.title = t.group(0)
        m.doc_type = "amendment" if "Amendment Directions" in m.title else "master_direction"
        m.md_family = _md_family(m.title)
        if p := _PARENTHETICAL.search(m.title):
            code = _ENTITY_CODES.get(_norm_entity(p.group(1)))
            m.entity_type_code = code

    # issued date = the first bare date in the header; effective from the set phrase.
    if hit := _ANY_DATE.search(text):
        m.issued_date = _parse_date(hit.group(0))
    if e := _EFFECTIVE.search(text):
        m.effective_date = _parse_date(e.group(1))
    elif _IMMEDIATE.search(text):
        m.effective_date = m.issued_date          # in force from the day it was issued

    m.missing = [
        f for f in ("rbi_ref", "title", "doc_type", "md_family",
                    "entity_type_code", "issued_date")
        if getattr(m, f) in (None, [])
    ]
    if m.missing:
        m.method = "regex+fallback-needed"
    return m
