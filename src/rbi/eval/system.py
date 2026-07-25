"""Baseline C — the full system under test (CLAUDE.md §9).

Ingests the sample corpus (parse via warm cache), builds the clause timeline and
change groups, and answers golden questions through the entity+validity resolver,
the change-group equivalence map, and group-membership cascade facts. It abstains
on anything not derivable from the ingested corpus (currently the two samples), so
questions about un-ingested entities (e.g. SFB) are honest coverage gaps.
"""
from __future__ import annotations

from pathlib import Path

from ..apply.build import build_timeline
from ..apply.models import ClauseVersion
from ..apply.resolve import resolve
from ..classify.rules import classify_text
from ..config import SAMPLES_DIR, config
from ..extract.normalise import normalise
from ..extract.pdf import extract_pdf
from ..group.build import group_ops
from ..group.models import ChangeGroup, OpRef
from ..parse.runner import parse_document
from .golden import GoldenQuestion
from .metrics import Prediction


class FullSystem:
    def __init__(self, versions: list[ClauseVersion], groups: list[ChangeGroup]):
        self.versions = versions
        self.groups = groups

    # --- ingestion ---
    @classmethod
    def from_samples(cls, *, model: str | None = None) -> "FullSystem":
        model = model or config.ollama_model_parse
        entries, ops = [], []
        for p in sorted(Path(SAMPLES_DIR).glob("*.pdf")):
            text = normalise(extract_pdf(p))
            meta = classify_text(text)
            result = parse_document(text, model=model)
            entries.append((meta, result.operations))
            for op in result.operations:
                if op.operation == "insert":
                    ops.append(
                        OpRef(
                            op_ref=f"{meta.rbi_ref}#seq{op.seq}",
                            entity_type_code=meta.entity_type_code,
                            md_family=meta.md_family,
                            issued_date=meta.issued_date,
                            effective_date=meta.effective_date,
                            text=" ".join(nc.text for nc in op.new_clauses),
                            clause_numbers=op.clause_numbers,
                        )
                    )
        return cls(build_timeline(entries), group_ops(ops))

    # --- answering ---
    def answer(self, q: GoldenQuestion) -> Prediction:
        if q.category in ("lookup", "temporal_trap", "entity_trap", "non_existent"):
            r = resolve(
                self.versions, md_family=q.md_family, entity_type_code=q.entity_type,
                clause_number=q.clause, as_of=q.as_of,
            )
            in_force = r.status == "in_force"
            return Prediction(
                status=r.status,
                text=r.text,
                clause=q.clause if in_force else None,
                # the filtered system only ever returns the asked entity's in-force text
                answer_entity=q.entity_type if in_force else None,
                answer_valid_from=r.valid_from if in_force else None,
                answer_valid_to=r.valid_to if in_force else None,
            )
        if q.category == "cross_entity":
            clause = self._equivalent(q.reference_entity, q.reference_clause, q.entity_type)
            if clause:
                return Prediction(status="equivalence", clause=clause)
            return Prediction(status="abstain", note="target entity not in ingested corpus")
        if q.category == "cascade":
            grp = self._group_for(q.entity_type, q.clause) if q.clause else None
            if grp:
                return Prediction(status="cascade", entities=grp.entity_codes,
                                  note="change-group members")
            return Prediction(status="abstain", note="not derivable from ingested corpus")
        return Prediction(status="abstain")

    # --- helpers ---
    def _group_for(self, entity: str | None, clause: str | None):
        for g in self.groups:
            for m in g.members:
                if m.entity_type_code == entity and clause in m.clause_numbers:
                    return g
        return None

    def _equivalent(self, ref_entity, ref_clause, target_entity) -> str | None:
        """Map a (ref_entity, ref_clause) to target_entity's clause by positional index."""
        g = self._group_for(ref_entity, ref_clause)
        if not g:
            return None
        ref_member = next((m for m in g.members if m.entity_type_code == ref_entity), None)
        tgt_member = next((m for m in g.members if m.entity_type_code == target_entity), None)
        if not ref_member or not tgt_member:
            return None
        idx = ref_member.clause_numbers.index(ref_clause)
        if idx < len(tgt_member.clause_numbers):
            return tgt_member.clause_numbers[idx]
        return None
