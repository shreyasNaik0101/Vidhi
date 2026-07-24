"""Stage 2–3: extract (pymupdf) + normalise. No LLM."""
from .normalise import normalise
from .pdf import extract_pdf, sha256_file

__all__ = ["extract_pdf", "sha256_file", "normalise"]
