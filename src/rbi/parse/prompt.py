"""Prompt for the parse stage (PROJECT_SPEC.md §6.4). JSON only, SHORT output.

The model must NOT reproduce clause text — only list clause_numbers. Long output
dominates CPU latency and risks truncation; the body is extracted deterministically.
"""
from __future__ import annotations

_SYSTEM = """\
You convert an RBI amendment's operative section into structured JSON operations.

Output ONLY a JSON object. No prose, no markdown, no code fences. Keep it SHORT.

Schema:
{
  "operations": [
    {
      "seq": <int, the (i)/(ii) order>,
      "operation": "insert" | "substitute" | "omit" | "unresolved",
      "target_chapter": <str or null, e.g. "V">,
      "target_anchor": <str or null, the clause an op attaches to; null for chapter-level>,
      "section_heading": <str or null, e.g. "B." or "E1.">,
      "clause_numbers": [<str>, ...],   // e.g. ["68C","68D"] — numbers ONLY, never the text
      "evidence_span": <str, ONE short sentence copied VERBATIM from the input that proves this operation>,
      "confidence": <float 0..1>
    }
  ]
}

Rules:
- Do NOT output clause text. List only the clause numbers in "clause_numbers".
- evidence_span MUST be copied verbatim from the input, character for character, and kept short.
- "insert" adds new clauses, "substitute" replaces text, "omit" deletes.
- If the target is ambiguous or you are unsure, use "operation":"unresolved" with
  "confidence" below 0.5. Never guess a target.
"""


def build_prompt(operative_text: str) -> str:
    return f'{_SYSTEM}\nInput:\n"""\n{operative_text}\n"""\n\nJSON:'
