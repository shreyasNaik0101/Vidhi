"""Parse stage CLI. `python -m rbi.parse.cli --limit 1 --model gemma4:latest`."""
from __future__ import annotations

from pathlib import Path

import typer

from ..config import SAMPLES_DIR, config
from ..extract.normalise import normalise
from ..extract.pdf import extract_pdf
from .postprocess import ParseError
from .runner import parse_document

app = typer.Typer(add_completion=False, help="Parse amendments into structured operations.")


@app.command()
def run(
    source: Path = typer.Option(SAMPLES_DIR, help="Directory of PDFs."),
    model: str = typer.Option(config.ollama_model_parse, help="Ollama model to use."),
    limit: int = typer.Option(1, help="Process at most N (test small first)."),
) -> None:
    pdfs = sorted(Path(source).glob("*.pdf"))[: limit or None]
    for p in pdfs:
        text = normalise(extract_pdf(p))
        try:
            result = parse_document(text, model=model)
        except ParseError as e:
            typer.echo(f"{p.name}: PARSE FAILED — {e}")
            continue
        for op in result.operations:
            clauses = ",".join(c.clause_number for c in op.new_clauses) or "-"
            typer.echo(
                f"{p.name}: seq={op.seq} {op.operation} "
                f"ch={op.target_chapter} heading={op.section_heading} "
                f"clauses={clauses} conf={op.confidence}"
                + (f"  note={op.note}" if op.note else "")
            )


if __name__ == "__main__":
    app()
