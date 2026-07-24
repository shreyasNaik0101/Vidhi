"""Domain types for the clause timeline (CLAUDE.md §5, §6.6)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

# in_force        -> a version applies on as_of
# not_yet_in_force-> the clause exists but its earliest version starts after as_of
# no_longer_in_force -> every version was closed (omitted/superseded) on or before as_of
# no_provision    -> the clause never exists for this entity
ResolutionStatus = Literal[
    "in_force", "not_yet_in_force", "no_longer_in_force", "no_provision"
]


@dataclass
class ClauseVersion:
    md_family: str
    entity_type_code: str
    clause_number: str
    sort_key: str
    chapter: str | None
    text: str
    valid_from: date              # = effective_date of the creating amendment
    valid_to: date | None = None  # None => currently in force
    created_by_ref: str | None = None    # e.g. amendment rbi_ref + seq
    superseded_by_ref: str | None = None


@dataclass
class Resolution:
    status: ResolutionStatus
    md_family: str
    entity_type_code: str
    clause_number: str
    as_of: date
    text: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    effective_date: date | None = None   # set for not_yet_in_force: when it starts
    note: str | None = None
    # every version considered, for a transparent abstention (UI shows these)
    candidates: list[ClauseVersion] = field(default_factory=list)

    @property
    def answered(self) -> bool:
        return self.status == "in_force"
