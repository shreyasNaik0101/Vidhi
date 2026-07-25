"""Scoring for the golden set (CLAUDE.md §9).

Always report accuracy AND coverage together. A system that abstains on everything
scores 100% accuracy and is useless — so coverage is measured over *answerable*
questions (those with a substantive expected answer), and a value below 60% is
flagged. Entity- and temporal-error rates must stay at zero: the entity + validity
filter exists precisely to prevent returning the wrong entity's or wrong era's text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .golden import GoldenQuestion

# A question has a substantive answer to give (vs. one where abstention is correct).
ANSWERABLE = {"in_force", "equivalence", "cascade"}


@dataclass
class Prediction:
    status: str                       # in_force|not_yet_in_force|no_provision|equivalence|cascade|abstain
    text: str | None = None
    clause: str | None = None
    entities: list[str] = field(default_factory=list)
    note: str = ""
    # provenance of a committed answer — lets error rates be measured for any baseline
    answer_entity: str | None = None
    answer_valid_from: date | None = None
    answer_valid_to: date | None = None


def committed(p: Prediction) -> bool:
    """Did the system commit to a substantive answer (vs. abstain)?"""
    return p.status in ANSWERABLE


def is_correct(q: GoldenQuestion, p: Prediction) -> bool:
    if q.category == "lookup":
        return p.status == "in_force" and (
            not q.expected_contains or (p.text is not None and q.expected_contains in p.text)
        )
    if q.category == "temporal_trap":
        return p.status == "not_yet_in_force"
    if q.category in ("entity_trap", "non_existent"):
        return p.status == "no_provision"
    if q.category == "cross_entity":
        return p.status == "equivalence" and p.clause == q.expected_clause
    if q.category == "cascade":
        if q.expected_entities:
            return p.status == "cascade" and set(q.expected_entities).issubset(set(p.entities))
        return False  # scalar cascade facts need the document layer (corpus-limited)
    return False


def is_entity_error(q: GoldenQuestion, p: Prediction) -> bool:
    """A committed answer whose text belongs to a different entity than asked."""
    if not committed(p) or not q.entity_type:
        return False
    if p.answer_entity is not None:
        return p.answer_entity != q.entity_type
    # fallback for baselines that don't report provenance: an in-force answer to an
    # entity-trap question can only be another entity's text.
    return q.category == "entity_trap"


def is_temporal_error(q: GoldenQuestion, p: Prediction) -> bool:
    """A committed answer whose text was not in force on as_of."""
    if not committed(p) or q.as_of is None:
        return False
    if p.answer_valid_from is not None:
        if q.as_of < p.answer_valid_from:
            return True
        if p.answer_valid_to is not None and q.as_of >= p.answer_valid_to:
            return True
        return False
    return q.category == "temporal_trap"


@dataclass
class Outcome:
    id: str
    category: str
    expected_status: str
    pred_status: str
    correct: bool
    committed: bool
    answerable: bool
    entity_error: bool
    temporal_error: bool


@dataclass
class Report:
    baseline: str
    outcomes: list[Outcome]
    cost_usd: float = 0.0

    @property
    def total(self) -> int:
        return len(self.outcomes)

    @property
    def overall_accuracy(self) -> float:
        return _safe(sum(o.correct for o in self.outcomes), self.total)

    @property
    def answered(self) -> int:
        return sum(o.committed for o in self.outcomes)

    @property
    def accuracy_on_answered(self) -> float:
        committed = [o for o in self.outcomes if o.committed]
        return _safe(sum(o.correct for o in committed), len(committed))

    @property
    def coverage(self) -> float:
        """Answered / answerable — over questions that have a real answer to give."""
        answerable = [o for o in self.outcomes if o.answerable]
        return _safe(sum(o.committed for o in answerable), len(answerable))

    @property
    def entity_error_rate(self) -> float:
        return _safe(sum(o.entity_error for o in self.outcomes), self.total)

    @property
    def temporal_error_rate(self) -> float:
        return _safe(sum(o.temporal_error for o in self.outcomes), self.total)

    @property
    def cost_per_100(self) -> float:
        return self.cost_usd / self.total * 100 if self.total else 0.0

    def by_category(self) -> dict[str, tuple[int, int]]:
        out: dict[str, list[int]] = {}
        for o in self.outcomes:
            c = out.setdefault(o.category, [0, 0])
            c[0] += int(o.correct)
            c[1] += 1
        return {k: (v[0], v[1]) for k, v in out.items()}


def _safe(num: int, den: int) -> float:
    return num / den if den else 0.0


def score(baseline: str, golden: list[GoldenQuestion], predict, cost_usd: float = 0.0) -> Report:
    outcomes = []
    for q in golden:
        p = predict(q)
        outcomes.append(
            Outcome(
                id=q.id,
                category=q.category,
                expected_status=q.expected_status,
                pred_status=p.status,
                correct=is_correct(q, p),
                committed=committed(p),
                answerable=q.expected_status in ANSWERABLE,
                entity_error=is_entity_error(q, p),
                temporal_error=is_temporal_error(q, p),
            )
        )
    return Report(baseline=baseline, outcomes=outcomes, cost_usd=cost_usd)
