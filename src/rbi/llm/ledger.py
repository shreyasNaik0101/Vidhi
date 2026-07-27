"""Cost ledger + spend cap (PROJECT_SPEC.md §7).

Every paid call records a row here. Before a paid call, `guard()` sums spend to date
and refuses if the call would breach MAX_SPEND_USD. AWS will not protect you — this does.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..config import config
from ._sqlite import connect

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_call (
    id            INTEGER PRIMARY KEY,
    ts            TEXT NOT NULL,
    model         TEXT NOT NULL,
    stage         TEXT NOT NULL,
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    est_cost_usd  REAL NOT NULL,
    cache_hit     INTEGER NOT NULL
);
"""


class SpendCapExceeded(RuntimeError):
    """Raised when a prospective paid call would breach MAX_SPEND_USD."""


class CostLedger:
    def __init__(self, path: Path | None = None, cap_usd: float | None = None):
        self._path = path
        self.cap_usd = config.max_spend_usd if cap_usd is None else cap_usd
        with connect(self._path) as c:
            c.execute(_SCHEMA)

    def record(
        self,
        *,
        model: str,
        stage: str,
        input_tokens: int,
        output_tokens: int,
        est_cost_usd: float,
        cache_hit: bool,
    ) -> None:
        with connect(self._path) as c:
            c.execute(
                "INSERT INTO llm_call "
                "(ts, model, stage, input_tokens, output_tokens, est_cost_usd, cache_hit) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    model,
                    stage,
                    input_tokens,
                    output_tokens,
                    est_cost_usd,
                    int(cache_hit),
                ),
            )

    def spend_to_date(self) -> float:
        """Total real spend. Cache hits cost nothing, so they are excluded."""
        with connect(self._path) as c:
            row = c.execute(
                "SELECT COALESCE(SUM(est_cost_usd), 0.0) AS s "
                "FROM llm_call WHERE cache_hit = 0"
            ).fetchone()
        return float(row["s"])

    def guard(self, prospective_cost_usd: float) -> None:
        """Call before every paid request. Raises if it would breach the cap."""
        projected = self.spend_to_date() + prospective_cost_usd
        if projected > self.cap_usd:
            raise SpendCapExceeded(
                f"Call (~${prospective_cost_usd:.4f}) would push spend to "
                f"${projected:.4f}, over cap ${self.cap_usd:.2f}. Stopping."
            )

    def by_stage(self) -> list[tuple[str, float, int]]:
        with connect(self._path) as c:
            return [
                (r["stage"], float(r["s"]), int(r["n"]))
                for r in c.execute(
                    "SELECT stage, SUM(est_cost_usd) AS s, COUNT(*) AS n "
                    "FROM llm_call GROUP BY stage ORDER BY s DESC"
                )
            ]

    def by_model(self) -> list[tuple[str, float, int]]:
        with connect(self._path) as c:
            return [
                (r["model"], float(r["s"]), int(r["n"]))
                for r in c.execute(
                    "SELECT model, SUM(est_cost_usd) AS s, COUNT(*) AS n "
                    "FROM llm_call GROUP BY model ORDER BY s DESC"
                )
            ]
