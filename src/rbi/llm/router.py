"""Model router (PROJECT_SPEC.md §7). route(task, difficulty) -> model.

Escalation is explicit and logged, never implicit — so the accuracy-vs-cost table
can be built from real routing decisions.
"""
from __future__ import annotations

import logging

from ..config import config

log = logging.getLogger("rbi.llm.router")

# Default model per task. Local (free) where possible; Bedrock only for verify.
_DEFAULT: dict[str, str] = {
    "classify": config.ollama_model_extract,   # gemma3:4b
    "extract": config.ollama_model_extract,    # gemma3:4b
    "parse": config.ollama_model_parse,        # qwen3:8b
    "group_confirm": config.ollama_model_parse,
    "verify": config.bedrock_model_id,         # cheap Bedrock model
}

# Where a task escalates when difficulty == "hard" (e.g. verifier disagreement).
_ESCALATION: dict[str, str] = {
    "verify": config.bedrock_escalation_model_id,
}


def route(task: str, difficulty: str = "normal") -> str:
    if task not in _DEFAULT:
        raise KeyError(f"Unknown task {task!r}; add it to router._DEFAULT")
    if difficulty == "hard" and task in _ESCALATION:
        model = _ESCALATION[task]
        log.info("route escalate task=%s difficulty=%s -> %s", task, difficulty, model)
        return model
    model = _DEFAULT[task]
    log.info("route task=%s difficulty=%s -> %s", task, difficulty, model)
    return model
