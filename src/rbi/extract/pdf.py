"""Raw text extraction with pymupdf (PROJECT_SPEC.md §6.2)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz  # pymupdf


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extract_pdf(path: str | Path) -> str:
    """Concatenate per-page text in reading order. Normalisation happens downstream."""
    doc = fitz.open(path)
    try:
        return "".join(page.get_text() for page in doc)
    finally:
        doc.close()
