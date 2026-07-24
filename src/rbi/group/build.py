"""Cluster operations into change groups (CLAUDE.md §6.7).

Within a single issued_date, connect operations whose new_text similarity clears
a threshold, then take connected components as groups. Similarity defaults to the
deterministic word-level measure (the stored score); pass an embedding-based
callable to cluster on cosine instead.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from .models import ChangeGroup, ChangeGroupMember, OpRef
from .similarity import word_similarity

SimFn = Callable[[str, str], float]
DEFAULT_THRESHOLD = 0.85


def _label_for(text: str) -> str:
    if "SNFA" in text or "Specified Non-Financial Asset" in text:
        return "SNFA income recognition"
    return "unlabelled change"


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i: int, j: int) -> None:
        self.parent[self.find(i)] = self.find(j)


def group_ops(
    ops: list[OpRef],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    similarity_fn: SimFn = word_similarity,
    singletons: bool = False,
) -> list[ChangeGroup]:
    """Return change groups. By default only groups with >= 2 members are returned."""
    groups: list[ChangeGroup] = []

    by_date: dict = defaultdict(list)
    for op in ops:
        by_date[(op.issued_date, op.md_family)].append(op)

    for (issued, family), bucket in sorted(by_date.items()):
        n = len(bucket)
        uf = _UnionFind(n)
        best: list[float] = [0.0] * n
        for i in range(n):
            for j in range(i + 1, n):
                sim = similarity_fn(bucket[i].text, bucket[j].text)
                if sim >= threshold:
                    uf.union(i, j)
                    best[i] = max(best[i], sim)
                    best[j] = max(best[j], sim)

        comps: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            comps[uf.find(i)].append(i)

        for members in comps.values():
            if len(members) < 2 and not singletons:
                continue
            reps = [
                ChangeGroupMember(
                    op_ref=bucket[i].op_ref,
                    entity_type_code=bucket[i].entity_type_code,
                    clause_numbers=bucket[i].clause_numbers,
                    similarity=round(best[i], 4),
                )
                for i in members
            ]
            eff = next((bucket[i].effective_date for i in members
                        if bucket[i].effective_date), None)
            groups.append(
                ChangeGroup(
                    label=_label_for(bucket[members[0]].text),
                    md_family=family,
                    issued_date=issued,
                    effective_date=eff,
                    members=sorted(reps, key=lambda m: m.entity_type_code),
                )
            )
    return groups
