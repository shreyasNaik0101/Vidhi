"""FastAPI ingestion service. POST /ingest streams the pipeline stage-by-stage.

Run: uvicorn rbi.ingest.service:app --port 8000   (PYTHONPATH=src)

Streams newline-delimited JSON so the UI can reveal each stage as it finishes —
extract → classify → parse (the slow local-model step) → apply → persist. The
persisted clause is immediately queryable through the normal read API.
"""
from __future__ import annotations

import hashlib
import json
from typing import Iterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..apply.build import assert_no_overlap, build_timeline
from ..classify.rules import classify_text
from ..config import config
from ..extract.normalise import normalise
from ..parse.runner import parse_document
from ..parse.section import operative_section
from .persist import persist_one
from ..db.sync import DocBundle

app = FastAPI(title="RBI ingestion")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class IngestRequest(BaseModel):
    text: str
    persist: bool = True
    model: str | None = None


def _event(stage: str, **data) -> str:
    return json.dumps({"stage": stage, **data}) + "\n"


def _run(text: str, model: str, do_persist: bool) -> Iterator[str]:
    try:
        yield _event("start", message="received amendment text")

        clean = normalise(text)
        yield _event("extract", chars=len(clean), preview=clean[:600])

        meta = classify_text(clean)
        yield _event(
            "classify",
            rbi_ref=meta.rbi_ref, entity=meta.entity_type_code, family=meta.md_family,
            doc_type=meta.doc_type, method=meta.method,
            issued=str(meta.issued_date) if meta.issued_date else None,
            effective=str(meta.effective_date) if meta.effective_date else None,
            missing=meta.missing,
        )

        _ = operative_section(clean)
        yield _event("parsing", message=f"running {model} — this is the slow step")
        result = parse_document(clean, model=model)
        yield _event(
            "parse",
            operations=[
                {
                    "seq": o.seq, "operation": o.operation, "chapter": o.target_chapter,
                    "section": o.section_heading, "confidence": o.confidence,
                    "evidence": o.evidence_span,
                    "clauses": [{"number": c.clause_number, "text": c.text} for c in o.new_clauses],
                }
                for o in result.operations
            ],
        )

        versions = build_timeline([(meta, result.operations)])
        assert_no_overlap(versions)
        yield _event(
            "apply",
            clauses=[{"clause": v.clause_number, "valid_from": str(v.valid_from)} for v in versions],
        )

        if do_persist and meta.entity_type_code and meta.rbi_ref and versions:
            bundle = DocBundle(
                meta=meta, operations=result.operations, source_url="pasted://ingest",
                sha256=hashlib.sha256(clean.encode("utf-8")).hexdigest(), raw_text=clean,
            )
            counts = persist_one(bundle, versions)
            yield _event(
                "persist", **counts,
                query={"entity": meta.entity_type_code, "family": meta.md_family,
                       "clause": versions[0].clause_number},
            )
        elif do_persist:
            yield _event("persist", skipped="need entity, ref and at least one clause to persist")

        yield _event("done")
    except Exception as e:  # surface any failure as a stream event, not a 500
        yield _event("error", message=str(e))


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/example")
def example() -> dict:
    """Real amendment text (from the committed sample) to prefill the ingest box."""
    from glob import glob

    from ..config import SAMPLES_DIR
    from ..extract.normalise import normalise
    from ..extract.pdf import extract_pdf

    for path in sorted(glob(str(SAMPLES_DIR / "*.pdf"))):
        text = normalise(extract_pdf(path))
        if "RBI/2026-27/201" in text:  # the Regional Rural Banks amendment
            return {"text": text}
    return {"text": ""}


@app.post("/ingest")
def ingest(req: IngestRequest) -> StreamingResponse:
    model = req.model or config.ollama_model_parse
    return StreamingResponse(
        _run(req.text, model, req.persist), media_type="application/x-ndjson",
    )
