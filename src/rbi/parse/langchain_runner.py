"""LangChain parse backend — an LCEL chain over the same local Ollama model.

An alternative to the native direct-HTTP parser (`parse.runner`). It builds the
same prompt, runs it through a LangChain `ChatOllama | StrOutputParser` chain with
grammar-constrained JSON, and feeds the raw output to the SAME deterministic
validators (`parse.postprocess`) — so the two backends are behaviourally
interchangeable and share every hallucination guard (verbatim evidence-span check,
confidence floor, clause-body slicing).

Selectable at runtime with `PARSE_BACKEND=langchain`. LangChain is an optional
dependency (`pip install -e ".[langchain]"`); it is imported lazily so the native
backend never requires it.
"""
from __future__ import annotations

from ..config import config
from .postprocess import ParseResult, postprocess
from .prompt import build_prompt
from .section import operative_section


def parse_document_langchain(
    normalised_text: str,
    *,
    model: str | None = None,
) -> ParseResult:
    """Parse one amendment's normalised text via a LangChain LCEL chain."""
    from langchain_core.output_parsers import StrOutputParser
    from langchain_ollama import ChatOllama

    model = model or config.ollama_model_parse
    section = operative_section(normalised_text)

    llm = ChatOllama(
        model=model,
        format="json",              # grammar-constrained JSON, like the native path
        temperature=0,
        num_ctx=config.ollama_num_ctx,
    )
    chain = llm | StrOutputParser()  # LCEL: model piped into the string parser
    raw = chain.invoke(build_prompt(section))

    return postprocess(raw, source=section)
