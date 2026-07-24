"""DB CLI: sync the pipeline into Postgres, and resolve as-of against it.

    python -m rbi.db.cli sync --model gemma4:latest
    python -m rbi.db.cli resolve --entity RRB --clause 68C --as-of 2026-10-02
"""
from __future__ import annotations

from datetime import date

import typer

from ..config import config
from .conn import connect
from .queries import resolve_as_of
from .sync import sync_samples

app = typer.Typer(add_completion=False, help="Persist and query the clause timeline.")


@app.command()
def sync(model: str = typer.Option(config.ollama_model_parse, help="Ollama model for parse.")):
    counts = sync_samples(model=model)
    typer.echo("persisted: " + ", ".join(f"{k}={v}" for k, v in counts.items()))


@app.command()
def resolve(
    entity: str = typer.Option(..., help="Entity code, e.g. RRB."),
    clause: str = typer.Option(..., help="Clause number, e.g. 68C."),
    family: str = typer.Option("IRACP", help="MD family."),
    as_of: str = typer.Option(..., "--as-of", help="ISO date."),
):
    with connect() as conn:
        r = resolve_as_of(conn, md_family=family, entity_code=entity,
                          clause_number=clause, as_of=date.fromisoformat(as_of))
    if r.status == "in_force":
        typer.echo(f"[{r.as_of}] IN FORCE (since {r.valid_from}): {r.text}")
    else:
        typer.echo(f"[{r.as_of}] {r.status.upper()} — {r.note}")


if __name__ == "__main__":
    app()
