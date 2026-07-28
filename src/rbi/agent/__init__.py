"""Agentic query layer: a LangChain tool-calling agent (Groq) over the resolver.

The agent plans which tool to call, extracts the bank type + date, looks the rule
up through the same tested resolver the rest of the system uses, remembers the
conversation for follow-ups, and — crucially — abstains honestly instead of
guessing. It is the autonomous counterpart to the deterministic Ask endpoint.
"""
