"""Extract stage CLI. `python -m rbi.extract.cli --limit 2 --dry-run` (CLAUDE.md §13)."""
from __future__ import annotations

from pathlib import Path

import typer

from ..config import SAMPLES_DIR
from .normalise import normalise
from .pdf import extract_pdf, sha256_file

app = typer.Typer(add_completion=False, help="Extract + normalise RBI PDFs.")


@app.command()
def run(
    source: Path = typer.Option(SAMPLES_DIR, help="Directory of PDFs to process."),
    limit: int = typer.Option(0, help="Process at most N PDFs (0 = all). Test small first."),
    dry_run: bool = typer.Option(False, help="Print a summary, write nothing."),
) -> None:
    pdfs = sorted(Path(source).glob("*.pdf"))
    if limit:
        pdfs = pdfs[:limit]
    if not pdfs:
        typer.echo(f"No PDFs in {source}")
        raise typer.Exit(1)

    for p in pdfs:
        raw = extract_pdf(p)
        clean = normalise(raw)
        typer.echo(
            f"{p.name}  sha256={sha256_file(p)[:12]}  "
            f"raw={len(raw)}c  clean={len(clean)}c  lines={clean.count(chr(10)) + 1}"
        )
        if dry_run:
            typer.echo("  [dry-run] " + clean.splitlines()[0][:80] if clean else "")


if __name__ == "__main__":
    app()
