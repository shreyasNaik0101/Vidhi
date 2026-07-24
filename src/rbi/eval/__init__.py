"""Evaluation harness (CLAUDE.md §9). Golden set loader lives here.

The golden set is hand-labelled ground truth — committed, never regenerated.
"""
from .golden import GoldenQuestion, load_golden

__all__ = ["GoldenQuestion", "load_golden"]
