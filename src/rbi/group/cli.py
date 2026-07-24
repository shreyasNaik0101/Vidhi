"""Group stage CLI — the cross-entity fan-out.

Runs the pipeline on the samples, builds one OpRef per parsed operation, groups
near-identical changes, and prints each group's entity fan-out with similarity.

    python -m rbi.group.cli --model gemma4:latest [--embeddings]
"""
from __future__ import annotations

from pathlib import Path

import typer

from ..classify.rules import classify_text
from ..config import SAMPLES_DIR, config
from ..extract.normalise import normalise
from ..extract.pdf import extract_pdf
from ..parse.runner import parse_document
from .build import group_ops
from .models import OpRef
from .similarity import word_similarity

app = typer.Typer(add_completion=False, help="Group the same change across entity types.")


def _op_refs(model: str) -> list[OpRef]:
    ops: list[OpRef] = []
    for p in sorted(Path(SAMPLES_DIR).glob("*.pdf")):
        text = normalise(extract_pdf(p))
        meta = classify_text(text)
        result = parse_document(text, model=model)
        for op in result.operations:
            if op.operation != "insert":
                continue
            body = " ".join(nc.text for nc in op.new_clauses)
            ops.append(
                OpRef(
                    op_ref=f"{meta.rbi_ref}#seq{op.seq}",
                    entity_type_code=meta.entity_type_code,
                    md_family=meta.md_family,
                    issued_date=meta.issued_date,
                    effective_date=meta.effective_date,
                    text=body,
                    clause_numbers=op.clause_numbers,
                )
            )
    return ops


@app.command()
def run(
    model: str = typer.Option(config.ollama_model_parse, help="Ollama model for parse."),
    embeddings: bool = typer.Option(False, help="Cluster on Ollama embeddings (else word-level)."),
    threshold: float = typer.Option(0.85, help="Similarity threshold."),
) -> None:
    ops = _op_refs(model)
    sim_fn = word_similarity
    if embeddings:
        from .embed import embedding_similarity_fn
        sim_fn = embedding_similarity_fn(ops)

    groups = group_ops(ops, threshold=threshold, similarity_fn=sim_fn)
    typer.echo(f"{len(ops)} operations -> {len(groups)} change group(s)\n")
    for g in groups:
        typer.echo(f"[{g.label}]  {g.md_family}  issued {g.issued_date}  effective {g.effective_date}")
        for m in g.members:
            typer.echo(f"   {m.entity_type_code:5} {','.join(m.clause_numbers):10} "
                       f"sim={m.similarity}")


if __name__ == "__main__":
    app()
