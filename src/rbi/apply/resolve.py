"""The as-of resolver (CLAUDE.md §5). Entity + validity filter, then the answer.

This is the query that defines the product. It never guesses: if nothing is in
force on `as_of`, it abstains with a status that says *why* (not yet in force /
no longer in force / no provision) and lists the versions it considered.
"""
from __future__ import annotations

from datetime import date

from .models import ClauseVersion, Resolution


def resolve(
    versions: list[ClauseVersion],
    *,
    md_family: str,
    entity_type_code: str,
    clause_number: str,
    as_of: date,
) -> Resolution:
    # Entity + clause filter FIRST — semantics never cross entity types.
    candidates = [
        v
        for v in versions
        if v.md_family == md_family
        and v.entity_type_code == entity_type_code
        and v.clause_number == clause_number
    ]
    base = dict(
        md_family=md_family,
        entity_type_code=entity_type_code,
        clause_number=clause_number,
        as_of=as_of,
        candidates=sorted(candidates, key=lambda v: v.valid_from),
    )

    if not candidates:
        return Resolution(
            status="no_provision",
            note=f"clause {clause_number} does not exist for {entity_type_code}",
            **base,
        )

    for v in candidates:
        if v.valid_from <= as_of and (v.valid_to is None or v.valid_to > as_of):
            return Resolution(
                status="in_force",
                text=v.text,
                valid_from=v.valid_from,
                valid_to=v.valid_to,
                **base,
            )

    future = [v for v in candidates if v.valid_from > as_of]
    if future:
        soonest = min(future, key=lambda v: v.valid_from)
        return Resolution(
            status="not_yet_in_force",
            effective_date=soonest.valid_from,
            note=(
                f"clause {clause_number} was issued but comes into force "
                f"{soonest.valid_from}; on {as_of} the prior text (if any) applies"
            ),
            **base,
        )

    latest = max(candidates, key=lambda v: v.valid_from)
    return Resolution(
        status="no_longer_in_force",
        valid_to=latest.valid_to,
        note=f"clause {clause_number} was closed on {latest.valid_to}",
        **base,
    )
