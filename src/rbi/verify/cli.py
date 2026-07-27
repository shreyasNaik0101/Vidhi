"""Verify stage CLI. `python -m rbi.verify.cli --sample-rate 1.0` (verify all parses).

Uses the deterministic stub by default (free). `--bedrock` switches to the paid
second opinion, which accrues cost in the ledger — visible via `make cost`.
"""
from __future__ import annotations

from pathlib import Path

import typer

from ..config import CORPUS_DIR, SAMPLES_DIR, config
from ..extract.normalise import normalise
from ..extract.pdf import extract_pdf
from ..llm.ledger import CostLedger
from ..parse.runner import parse_document
from ..parse.section import operative_section
from .verifier import BedrockVerifier, StubVerifier, verify_operations

app = typer.Typer(add_completion=False, help="Independently verify parsed operations.")


def _texts() -> list[tuple[str, str]]:
    out = []
    for p in sorted(Path(SAMPLES_DIR).glob("*.pdf")):
        out.append((p.name, normalise(extract_pdf(p))))
    for p in sorted(Path(CORPUS_DIR).glob("*.txt")):
        out.append((p.name, normalise(p.read_text(encoding="utf-8"))))
    return out


@app.command()
def run(
    model: str = typer.Option(config.ollama_model_parse, help="Ollama model for parse."),
    bedrock: bool = typer.Option(False, help="Use the paid Bedrock verifier (needs AWS)."),
    sample_rate: float = typer.Option(1.0, help="Fraction of confident parses to verify."),
) -> None:
    verifier = BedrockVerifier() if bedrock else StubVerifier()
    ledger = CostLedger()
    before = ledger.spend_to_date()

    for name, text in _texts():
        result = parse_document(text, model=model)
        section = operative_section(text)
        results = verify_operations(result.operations, section,
                                    verifier=verifier, sample_rate=sample_rate, ledger=ledger)
        for r in results:
            typer.echo(f"{name}: seq {r.op_seq} -> {r.verdict.upper()}  ({r.model}) {r.notes}")

    spent = ledger.spend_to_date() - before
    typer.echo(f"\nverifier: {'Bedrock' if bedrock else 'stub'} | this run cost ${spent:.4f}")


if __name__ == "__main__":
    app()
