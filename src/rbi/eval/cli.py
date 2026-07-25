"""`make eval` — score baselines against the golden set and print metrics (§9).

Baseline A (naive RAG) reads the pgvector index; Baseline C (full system) uses the
entity+validity resolver. `compare` runs both and prints them side by side — the
entity/temporal error columns are where the difference lives.
"""
from __future__ import annotations

import typer

from ..config import config
from ..db.conn import connect
from ..group.embed import DEFAULT_EMBED_MODEL
from .golden import load_golden
from .metrics import Report, score
from .naive import NaiveRAG, build_index
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
    typer.echo("by category        correct / total")
    for cat, (correct, total) in sorted(r.by_category().items()):
        typer.echo(f"  {cat:14} {correct:3} / {total:<3}  {correct / total:5.0%}")


def _ensure_index(conn, model: str, rebuild: bool) -> int:
    with conn.cursor() as cur:
        try:
            cur.execute("SELECT count(*) FROM naive_chunk")
            n = cur.fetchone()[0]
        except Exception:
            conn.rollback()
            n = -1
    if rebuild or n <= 0:
        typer.echo("building naive-RAG index (embedding chunks)…")
        return build_index(conn, model=model)
    return n


@app.command()
def baseline_c(model: str = typer.Option(config.ollama_model_parse, help="Ollama parse model.")):
    """Score the full system."""
    render(score("C", load_golden(), FullSystem.from_samples(model=model).answer))


@app.command()
def build_naive_index(embed_model: str = typer.Option(DEFAULT_EMBED_MODEL)):
    """(Re)build the naive-RAG pgvector index from document text."""
    with connect() as conn:
        n = build_index(conn, model=embed_model)
    typer.echo(f"indexed {n} chunks")


@app.command()
def compare(
    model: str = typer.Option(config.ollama_model_parse, help="Ollama parse model (Baseline C)."),
    embed_model: str = typer.Option(DEFAULT_EMBED_MODEL, help="Embedding model (Baseline A)."),
    rebuild: bool = typer.Option(False, help="Rebuild the naive index first."),
):
    """Score Baseline A (naive RAG) and Baseline C (full system) side by side."""
    golden = load_golden()
    report_c = score("C", golden, FullSystem.from_samples(model=model).answer)

    with connect() as conn:
        _ensure_index(conn, embed_model, rebuild)
        rag = NaiveRAG(conn=conn, model=embed_model)
        report_a = score("A", golden, rag.answer)

    render(report_a)
    render(report_c)

    typer.echo("\n=== A (naive RAG)  vs  C (full system) ===")
    rows = [
        ("overall accuracy", report_a.overall_accuracy, report_c.overall_accuracy, "up"),
        ("coverage", report_a.coverage, report_c.coverage, "up"),
        ("entity error rate", report_a.entity_error_rate, report_c.entity_error_rate, "down"),
        ("temporal err rate", report_a.temporal_error_rate, report_c.temporal_error_rate, "down"),
    ]
    typer.echo(f"{'metric':20} {'A':>8} {'C':>8}   better")
    for label, a, c, better in rows:
        typer.echo(f"{label:20} {a:7.1%} {c:7.1%}   {'C' if ((c>a)==(better=='up')) else 'A'}")


if __name__ == "__main__":
    app()
