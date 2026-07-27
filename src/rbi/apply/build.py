"""Materialise clause versions from parsed operations (PROJECT_SPEC.md §6.7).

  insert     -> new version, valid_from = effective_date, valid_to = None
  substitute -> close the prior open version (valid_to = effective_date), add new
  omit       -> close the prior open version, add nothing
  unresolved -> not applied

After building, assert_no_overlap fails loudly if any (family, entity, clause) has
two versions with overlapping validity.
"""
from __future__ import annotations

import re
from datetime import date

from ..classify.rules import DocumentMeta
from ..parse.schema import Operation
from .models import ClauseVersion


def make_sort_key(clause_number: str) -> str:
    """'68C' -> '00068C', '119D' -> '00119D' — numeric prefix zero-padded, suffix kept."""
    m = re.match(r"(\d+)([A-Za-z]*)", clause_number.strip())
    if not m:
        return clause_number
    return f"{int(m.group(1)):05d}{m.group(2).upper()}"


def _effective(meta: DocumentMeta) -> date:
    if meta.effective_date is not None:
        return meta.effective_date
    if meta.issued_date is not None:
        return meta.issued_date
    raise ValueError(f"{meta.rbi_ref}: no issued_date to derive validity from")


def _key(v: ClauseVersion) -> tuple[str, str, str]:
    return (v.md_family, v.entity_type_code, v.clause_number)


def _open_version(versions: list[ClauseVersion], meta: DocumentMeta, number: str):
    want = (meta.md_family, meta.entity_type_code, number)
    for v in versions:
        if _key(v) == want and v.valid_to is None:
            return v
    return None


def build_timeline(
    entries: list[tuple[DocumentMeta, list[Operation]]],
) -> list[ClauseVersion]:
    """Apply operations in effective_date order and return all clause versions."""
    ordered = sorted(entries, key=lambda e: _effective(e[0]))
    versions: list[ClauseVersion] = []

    for meta, ops in ordered:
        eff = _effective(meta)
        for op in ops:
            ref = f"{meta.rbi_ref}#seq{op.seq}"
            if op.operation == "insert":
                for nc in op.new_clauses:
                    versions.append(
                        ClauseVersion(
                            md_family=meta.md_family,
                            entity_type_code=meta.entity_type_code,
                            clause_number=nc.clause_number,
                            sort_key=make_sort_key(nc.clause_number),
                            chapter=op.target_chapter,
                            text=nc.text,
                            valid_from=eff,
                            created_by_ref=ref,
                        )
                    )
            elif op.operation == "substitute":
                for nc in op.new_clauses:
                    prior = _open_version(versions, meta, nc.clause_number)
                    if prior is not None:
                        prior.valid_to = eff
                        prior.superseded_by_ref = ref
                    versions.append(
                        ClauseVersion(
                            md_family=meta.md_family,
                            entity_type_code=meta.entity_type_code,
                            clause_number=nc.clause_number,
                            sort_key=make_sort_key(nc.clause_number),
                            chapter=op.target_chapter,
                            text=nc.text,
                            valid_from=eff,
                            created_by_ref=ref,
                        )
                    )
            elif op.operation == "omit":
                numbers = op.clause_numbers or ([op.target_anchor] if op.target_anchor else [])
                for number in numbers:
                    prior = _open_version(versions, meta, number)
                    if prior is not None:
                        prior.valid_to = eff
                        prior.superseded_by_ref = ref
            # 'unresolved' is intentionally not applied
    return versions


def assert_no_overlap(versions: list[ClauseVersion]) -> None:
    """No (family, entity, clause) may have two versions valid at the same time."""
    groups: dict[tuple[str, str, str], list[ClauseVersion]] = {}
    for v in versions:
        groups.setdefault(_key(v), []).append(v)

    for key, vs in groups.items():
        vs = sorted(vs, key=lambda v: v.valid_from)
        for a, b in zip(vs, vs[1:]):
            a_end = a.valid_to
            if a_end is None or a_end > b.valid_from:
                raise AssertionError(
                    f"overlapping validity for {key}: "
                    f"[{a.valid_from}..{a_end}] and [{b.valid_from}..{b.valid_to}]"
                )
