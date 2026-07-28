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
    backend: str | None = None,
) -> ParseResult:
    """Parse one amendment's normalised text into validated operations.

    `backend` selects the LLM path: "native" (direct Ollama HTTP, with the response
    cache + cost ledger) or "langchain" (an LCEL chain over the same model). Both
    feed the same validators. Defaults to config.parse_backend (PARSE_BACKEND).
    """
    backend = backend or config.parse_backend
    if backend == "langchain":
        from .langchain_runner import parse_document_langchain
        return parse_document_langchain(normalised_text, model=model)

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
