"""Agent tools — thin wrappers over the real read path (DB + apply.resolve).

Each tool is a plain function the agent can call. They reuse the exact resolver
the API and CLI use, so the agent inherits its guarantees: entity + date filter
first, and an honest abstention (not-yet / no-longer / no-provision) when nothing
is in force. The tool never invents a rule.
"""
from __future__ import annotations

import re
from datetime import date

from langchain_core.tools import tool

from ..apply.models import Resolution
from ..db.conn import connect
from ..db.queries import load_clause_versions, resolve_as_of

FAMILY = "IRACP"


def _fmt(r: Resolution) -> str:
    if r.status == "in_force":
        span = f"{r.valid_from} to {r.valid_to or 'present'}"
        return (f"IN FORCE for {r.entity_type_code} clause {r.clause_number} "
                f"(valid {span}):\n{r.text}")
    if r.status == "not_yet_in_force":
        return (f"NOT YET IN FORCE: clause {r.clause_number} for {r.entity_type_code} "
                f"comes into force on {r.effective_date}. {r.note or ''}").strip()
    if r.status == "no_longer_in_force":
        return f"NO LONGER IN FORCE: {r.note or 'this clause was closed.'}"
    return (f"NO PROVISION: clause {r.clause_number} does not exist for "
            f"{r.entity_type_code}. {r.note or ''}").strip()


@tool
def resolve_clause(bank: str, clause: str, as_of: str) -> str:
    """Look up what a specific clause says for a bank type on a specific date.

    bank: entity code such as RRB, LAB, SFB, SCB, UCB, NBFC.
    clause: clause number such as 68C.
    as_of: the date to check, as ISO YYYY-MM-DD.
    Returns the exact rule text if it is in force, or an honest status
    (not yet in force / no longer in force / no provision) — never a guess.
    """
    with connect() as conn:
        r = resolve_as_of(conn, md_family=FAMILY, entity_code=bank.upper(),
                          clause_number=clause.upper(), as_of=date.fromisoformat(as_of))
    return _fmt(r)


@tool
def clause_history(bank: str, clause: str) -> str:
    """List every version of a clause over time for a bank type, oldest first."""
    with connect() as conn:
        vs = load_clause_versions(conn, md_family=FAMILY, entity_code=bank.upper(),
                                  clause_number=clause.upper())
    if not vs:
        return f"No versions on record for {bank.upper()} clause {clause.upper()}."
    return "\n".join(
        f"- {v.valid_from} to {v.valid_to or 'present'}: {v.text[:140]}…" for v in vs
    )


@tool
def find_clause(bank: str, topic: str) -> str:
    """Find which clause number covers a topic for a bank type (keyword match)."""
    with connect() as conn:
        vs = load_clause_versions(conn, md_family=FAMILY, entity_code=bank.upper())
    if not vs:
        return f"No clauses on record for {bank.upper()}."
    q = set(re.findall(r"[a-z0-9]+", topic.lower()))
    best, best_score = None, 0
    scores: dict[str, int] = {}
    for v in vs:
        hits = sum(1 for t in re.findall(r"[a-z0-9]+", v.text.lower()) if t in q)
        scores[v.clause_number] = max(scores.get(v.clause_number, 0), hits)
    for cn, sc in scores.items():
        if sc > best_score:
            best, best_score = cn, sc
    return (f"Clause {best} appears most relevant to “{topic}” for {bank.upper()}."
            if best else f"No clause clearly matches “{topic}” for {bank.upper()}.")


@tool
def list_banks() -> str:
    """List the bank types (entity codes) that have rules on record."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT e.code, e.name FROM clause c "
            "JOIN entity_type e ON e.id = c.entity_type_id ORDER BY e.code"
        )
        rows = cur.fetchall()
    return ", ".join(f"{code} ({name})" for code, name in rows) or "none loaded."


TOOLS = [resolve_clause, clause_history, find_clause, list_banks]
