"""Similarity measures for grouping (CLAUDE.md §6.7).

word_similarity is deterministic and needs no model — it reproduces the ~0.957
reference between the RRB and LAB SNFA clauses and is the stored score. cosine is
used when embeddings are available.
"""
from __future__ import annotations

import math
import re
from difflib import SequenceMatcher


def tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def word_similarity(a: str, b: str) -> float:
    """Word-level ratio in [0,1]. Tolerant of the RBI typos (no normalisation)."""
    return SequenceMatcher(None, tokenize(a), tokenize(b)).ratio()


def cosine(u: list[float], v: list[float]) -> float:
    if len(u) != len(v):
        raise ValueError("vector length mismatch")
    dot = sum(x * y for x, y in zip(u, v))
    nu = math.sqrt(sum(x * x for x in u))
    nv = math.sqrt(sum(y * y for y in v))
    if nu == 0 or nv == 0:
        return 0.0
    return dot / (nu * nv)
