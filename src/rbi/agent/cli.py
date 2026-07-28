"""Agent CLI: an interactive chat, or a single question.

    python -m rbi.agent.cli chat                 # multi-turn, with memory
    python -m rbi.agent.cli ask "SNFA income for a rural bank in November 2026"

Needs GROQ_API_KEY in the environment (or .env) and the database up (make db-up).
"""
from __future__ import annotations

import os

import typer
from langchain_core.messages import AIMessage, HumanMessage

from .agent import build_agent

app = typer.Typer(add_completion=False, help="Chat with the Vidhi regulatory agent.")


def _require_key() -> None:
    if not os.getenv("GROQ_API_KEY"):
        typer.secho("GROQ_API_KEY is not set. Add it to your environment or .env, "
                    "then retry.", fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def ask(question: str, model: str = typer.Option(None, help="Groq model override.")):
    """Answer one question and exit."""
    _require_key()
    executor = build_agent(model=model)
    out = executor.invoke({"input": question, "chat_history": []})
    typer.echo(out["output"])


@app.command()
def chat(model: str = typer.Option(None, help="Groq model override."),
         verbose: bool = typer.Option(False, help="Show the agent's tool calls.")):
    """Interactive multi-turn chat (remembers the conversation)."""
    _require_key()
    executor = build_agent(model=model, verbose=verbose)
    history: list = []
    typer.secho("Vidhi agent — ask about a banking rule. Ctrl-C to exit.\n",
                fg=typer.colors.CYAN)
    while True:
        try:
            q = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            typer.echo("\nbye")
            break
        if not q:
            continue
        out = executor.invoke({"input": q, "chat_history": history})
        answer = out["output"]
        typer.secho(f"vidhi> {answer}\n", fg=typer.colors.GREEN)
        history += [HumanMessage(content=q), AIMessage(content=answer)]


if __name__ == "__main__":
    app()
