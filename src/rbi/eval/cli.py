"""`make eval` — score a baseline against the golden set and print metrics (§9)."""
from __future__ import annotations

import typer

from ..config import config
from ..llm.ledger import CostLedger
from .golden import load_golden
from .metrics import Report, score
from .system import FullSystem

app = typer.Typer(add_completion=False, help="Score baselines against the golden set.")


def render(r: Report) -> None:
    typer.echo(f"\n=== Baseline {r.baseline} — {r.total} questions ===")
    typer.echo(f"overall accuracy   {r.overall_accuracy:6.1%}  (correct incl. correct abstentions)")
    typer.echo(f"coverage           {r.coverage:6.1%}  (answered / answerable)")
    typer.echo(f"accuracy@answered  {r.accuracy_on_answered:6.1%}  ({r.answered} answered)")
    typer.echo(f"entity error rate  {r.entity_error_rate:6.1%}")
    typer.echo(f"temporal err rate  {r.temporal_error_rate:6.1%}")
    typer.echo(f"cost / 100 Q       ${r.cost_per_100:.4f}")
    if r.coverage < 0.60:
        typer.echo("!! coverage below 60% on answerable questions — investigate corpus/abstention")

    typer.echo("\nby category        correct / total")
    for cat, (correct, total) in sorted(r.by_category().items()):
        typer.echo(f"  {cat:14} {correct:3} / {total:<3}  {correct / total:5.0%}")


@app.command()
def run(
    baseline: str = typer.Option("C", help="Which baseline (only C implemented locally)."),
    model: str = typer.Option(config.ollama_model_parse, help="Ollama model for parse."),
) -> None:
    golden = load_golden()
    if baseline.upper() != "C":
        raise typer.BadParameter("only Baseline C runs without pgvector/Bedrock")

    system = FullSystem.from_samples(model=model)
    before = CostLedger().spend_to_date()
    report = score("C", golden, system.answer, cost_usd=CostLedger().spend_to_date() - before)
    render(report)


if __name__ == "__main__":
    app()
