"""Build the tool-calling agent: Groq LLM + the resolver tools + conversation memory.

The system prompt encodes the product's core rule — an answer depends on the bank
type AND the date, and the agent must abstain rather than guess. The agent plans a
tool call, reads the result, and answers; `chat_history` gives it memory so
follow-ups like “and for a Local Area Bank?” reuse the earlier clause and date.
"""
from __future__ import annotations

from datetime import date

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq

from ..config import config
from .tools import TOOLS

_SYSTEM = f"""You are Vidhi, an assistant for Indian banking regulation (RBI Master Directions).

Non-negotiable rules:
- The correct answer depends on the BANK TYPE (an entity code like RRB, LAB, SFB) and the DATE. \
Work out both before answering. If either is missing from the conversation, ask the user for it — do not assume.
- Always use the tools to look a rule up. Never state a rule from your own memory.
- If a tool reports NOT YET IN FORCE, NO LONGER IN FORCE, or NO PROVISION, tell the user that plainly. \
Never substitute another bank's rule or another date's rule to seem helpful.
- Today's date is {date.today().isoformat()}. Resolve relative dates ("today", "now", "currently") against it.

Answer in plain, concise English. When you quote a rule, say which bank, clause, and date it is for.
"""


def build_agent(*, model: str | None = None, temperature: float = 0.0, verbose: bool = False) -> AgentExecutor:
    """Assemble the Groq-backed tool-calling agent. Requires GROQ_API_KEY in the env."""
    llm = ChatGroq(model=model or config.groq_model, temperature=temperature)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _SYSTEM),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, TOOLS, prompt)
    return AgentExecutor(agent=agent, tools=TOOLS, verbose=verbose, max_iterations=6,
                         handle_parsing_errors=True)
