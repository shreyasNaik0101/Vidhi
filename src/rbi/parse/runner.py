"""Orchestrates the parse stage: section -> prompt -> local model -> validated ops."""
from __future__ import annotations

from ..config import config
from ..llm.cache import ResponseCache
from ..llm.ledger import CostLedger
from .ollama_client import generate
from .postprocess import ParseResult, postprocess
from .prompt import build_prompt
from .section import operative_section


def parse_document(
    normalised_text: str,
    *,
    model: str | None = None,
    cache: ResponseCache | None = None,
    ledger: CostLedger | None = None,
) -> ParseResult:
    """Parse one amendment's normalised text into validated operations."""
    model = model or config.ollama_model_parse
    section = operative_section(normalised_text)
    raw = generate(
        build_prompt(section),
        model=model,
        stage="parse",
        cache=cache,
        ledger=ledger,
    )
    # Validate the model's claims against the section it was actually given.
    return postprocess(raw, source=section)
