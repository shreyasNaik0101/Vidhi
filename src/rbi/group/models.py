"""Domain types for change grouping (CLAUDE.md §5, §6.7)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class OpRef:
    """One operation, with the entity context needed to group it across entities."""
    op_ref: str                  # 'RBI/2026-27/201#seq1'
    entity_type_code: str
    md_family: str
    issued_date: date
    text: str                    # the operation's new_text (concatenated clause bodies)
    clause_numbers: list[str] = field(default_factory=list)
    effective_date: date | None = None


@dataclass
class ChangeGroupMember:
    op_ref: str
    entity_type_code: str
    clause_numbers: list[str]
    similarity: float            # best word-level similarity to another member


@dataclass
class ChangeGroup:
    label: str
    md_family: str
    issued_date: date
    effective_date: date | None
    members: list[ChangeGroupMember] = field(default_factory=list)

    @property
    def entity_codes(self) -> list[str]:
        return [m.entity_type_code for m in self.members]
