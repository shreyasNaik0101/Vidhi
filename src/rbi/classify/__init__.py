"""Stage 4: classify. Regex-first (§6.3), gemma3:4b fallback only when a regex misses.

Which path was used is recorded per document — the regex-hit rate is worth reporting.
"""
from .rules import DocumentMeta, classify_text

__all__ = ["DocumentMeta", "classify_text"]
