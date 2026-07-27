"""Classify stage CLI. `python -m rbi.classify.cli --limit 2` (PROJECT_SPEC.md §13).

Logs the regex-hit rate — the share of docs classified with no LLM fallback.
"""
from __future__ import annotations

from pathlib import Path

import typer

from ..config import SAMPLES_DIR
from ..extract.normalise import normalise
from ..extract.pdf import extract_pdf
from .rules import classify_text

app = typer.Typer(add_completion=False, help="Classify RBI documents (regex-first).")


@app.command()
def run(
    source: Path = typer.Option(SAMPLES_DIR, help="Directory of PDFs."),
    limit: int = typer.Option(0, help="Process at most N (0 = all)."),
    dry_run: bool = typer.Option(False, help="Print only, write nothing."),
) -> None:
    pdfs = sorted(Path(source).glob("*.pdf"))
    if limit:
        pdfs = pdfs[:limit]

    regex_hits = 0
    for p in pdfs:
        meta = classify_text(normalise(extract_pdf(p)))
        if not meta.missing:
            regex_hits += 1
        typer.echo(
            f"{meta.rbi_ref}  {meta.entity_type_code}/{meta.md_family}/{meta.doc_type}  "
            f"issued={meta.issued_date} effective={meta.effective_date}  "
            f"[{meta.method}]"
            + (f"  missing={meta.missing}" if meta.missing else "")
        )

    if pdfs:
        typer.echo(f"\nregex-hit rate: {regex_hits}/{len(pdfs)} "
                   f"({regex_hits / len(pdfs) * 100:.0f}%)")


if __name__ == "__main__":
    app()
