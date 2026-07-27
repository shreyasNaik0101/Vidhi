"""Stage 6: verify (PROJECT_SPEC.md §6.5) — an independent second check on each parse.

The parser's own deterministic guards (verbatim evidence span, clause extraction)
run first. This stage adds a *second opinion* on the borderline cases: only parses
with confidence between 0.5 and 0.9, plus a small calibration sample of the
high-confidence ones. The verifier can only confirm / correct / reject — it can
never invent a mapping.

Two implementations:
  - StubVerifier   — deterministic, no cloud, always available; re-checks the parse
                     against the source. Used in tests and when Bedrock is off.
  - BedrockVerifier — the paid step; a semantic second opinion, through the cache,
                     ledger and spend cap. Fills the cost column of the eval table.
"""
from .router import needs_verify
from .schema import VerifyResult
from .verifier import StubVerifier, verify_operations

__all__ = ["VerifyResult", "needs_verify", "StubVerifier", "verify_operations"]
