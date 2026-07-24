"""Apply stage CLI + the date-flip demo (Definition of Done #1).

Runs extract -> classify -> parse -> apply on the sample PDFs (parse hits the
warm cache), builds the timeline, and answers the same clause at two dates either
side of the effective date.

    python -m rbi.apply.cli --model gemma4:latest --clause 68C --entity RRB
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import typer

from ..classify.rules import classify_text
from ..config import SAMPLES_DIR, config
from ..extract.normalise import normalise
from ..extract.pdf import extract_pdf
from ..parse.runner import parse_document
from .build import assert_no_overlap, build_timeline
from .resolve import resolve

app = typer.Typer(add_completion=False, help="Build the clause timeline and resolve as-of.")


def _load_samples(model: str):
    entries = []
    for p in sorted(Path(SAMPLES_DIR).glob("*.pdf")):
        text = normalise(extract_pdf(p))
        meta = classify_text(text)
        result = parse_document(text, model=model)
        entries.append((meta, result.operations))
    return entries


def _show(r) -> None:
    if r.status == "in_force":
        typer.echo(f"  [{r.as_of}] IN FORCE (since {r.valid_from}): {r.text[:90]}...")
    else:
        typer.echo(f"  [{r.as_of}] {r.status.upper()} — {r.note}")


@app.command()
def run(
    model: str = typer.Option(config.ollama_model_parse, help="Ollama model for parse."),
    entity: str = typer.Option("RRB", help="Entity type code."),
    family: str = typer.Option("IRACP", help="Master Direction family."),
    clause: str = typer.Option("68C", help="Clause number."),
    before: str = typer.Option("2026-09-30", help="A date before the effective date."),
    after: str = typer.Option("2026-10-02", help="A date on/after the effective date."),
) -> None:
    entries = _load_samples(model)
    versions = build_timeline(entries)
    assert_no_overlap(versions)
    typer.echo(f"built {len(versions)} clause version(s)\n")

    typer.echo(f"{family} clause {clause} for {entity} — the date flip:")
    for d in (before, after):
        _show(resolve(versions, md_family=family, entity_type_code=entity,
                      clause_number=clause, as_of=date.fromisoformat(d)))

    # entity trap: LAB's clause number asked of an RRB
    typer.echo("\nentity trap (LAB clause 119C asked of RRB):")
    _show(resolve(versions, md_family=family, entity_type_code=entity,
                  clause_number="119C", as_of=date.fromisoformat(after)))


if __name__ == "__main__":
    app()
