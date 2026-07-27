"""Verifiers + the verify stage.

`verify_operations` routes the uncertain parses to a verifier, records the call in
the ledger, and downgrades any the verifier rejects to 'unresolved' (never guesses).
"""
from __future__ import annotations

import re

from ..config import config
from ..llm.cache import ResponseCache
from ..llm.ledger import CostLedger
from ..llm.pricing import estimate_cost_usd
from ..parse.schema import Operation
from .router import needs_verify
from .schema import VerifyResult


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _verbatim(span: str, source: str) -> bool:
    return bool(span.strip()) and _norm(span) in _norm(source)


class StubVerifier:
    """Deterministic second check — no cloud. Re-validates the parse against source:
    the evidence span must be verbatim and every named clause must appear in the text."""

    model = "stub"

    def verify(self, op: Operation, source: str) -> VerifyResult:
        if not _verbatim(op.evidence_span, source):
            return VerifyResult(op.seq, "reject", notes="evidence span not verbatim in source",
                                model=self.model)
        missing = [n for n in op.clause_numbers if _norm(n) not in _norm(source)]
        if missing:
            return VerifyResult(op.seq, "reject", notes=f"clauses not found in source: {missing}",
                                model=self.model)
        return VerifyResult(op.seq, "confirm", notes="deterministic re-check passed",
                            model=self.model)


_PROMPT = """\
You independently verify a parsed RBI amendment operation against its source text.
Reply with exactly one word: CONFIRM, CORRECT, or REJECT.

Operation: {operation} | chapter {chapter} | clauses {clauses}
Evidence the parser cited: "{evidence}"

Source:
\"\"\"
{source}
\"\"\"
Reply CONFIRM if the operation and clauses are exactly supported by the source,
REJECT if not, CORRECT if the source supports a different operation/clauses."""


class BedrockVerifier:
    """The paid second opinion (Bedrock). Goes through the cache, ledger and spend cap.
    Requires AWS credentials + an enabled region; never invoked by the test suite."""

    def __init__(self, *, model: str | None = None, region: str | None = None,
                 cache: ResponseCache | None = None, ledger: CostLedger | None = None):
        self.model = model or config.bedrock_model_id
        self.region = region or config.aws_region
        self.cache = cache or ResponseCache()
        self.ledger = ledger or CostLedger()

    def _prompt(self, op: Operation, source: str) -> str:
        return _PROMPT.format(operation=op.operation, chapter=op.target_chapter,
                              clauses=",".join(op.clause_numbers), evidence=op.evidence_span,
                              source=source)

    def verify(self, op: Operation, source: str) -> VerifyResult:
        import json

        prompt = self._prompt(op, source)
        hit = self.cache.get(self.model, prompt)
        if hit is not None:
            self.ledger.record(model=self.model, stage="verify", input_tokens=0,
                               output_tokens=0, est_cost_usd=0.0, cache_hit=True)
            return self._verdict(op.seq, hit)

        est = estimate_cost_usd(self.model, len(prompt) // 4, 8)
        self.ledger.guard(est)                       # refuse if it would breach the cap

        import boto3

        client = boto3.client("bedrock-runtime", region_name=self.region)
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31", "max_tokens": 8,
            "messages": [{"role": "user", "content": prompt}],
        })
        resp = client.invoke_model(modelId=self.model, body=body)
        payload = json.loads(resp["body"].read())
        text = payload["content"][0]["text"]
        usage = payload.get("usage", {})
        cost = estimate_cost_usd(self.model, usage.get("input_tokens", 0), usage.get("output_tokens", 0))
        self.ledger.record(model=self.model, stage="verify",
                           input_tokens=usage.get("input_tokens", 0),
                           output_tokens=usage.get("output_tokens", 0),
                           est_cost_usd=cost, cache_hit=False)
        self.cache.put(self.model, prompt, text)
        return self._verdict(op.seq, text, cost)

    def _verdict(self, seq: int, text: str, cost: float = 0.0) -> VerifyResult:
        t = text.strip().upper()
        verdict = "confirm" if "CONFIRM" in t else "reject" if "REJECT" in t else "correct"
        return VerifyResult(seq, verdict, notes=text.strip()[:120], model=self.model, est_cost_usd=cost)


def verify_operations(operations, source, *, verifier=None, sample_rate: float = 0.10,
                      rng=None, ledger: CostLedger | None = None) -> list[VerifyResult]:
    """Verify the routed operations; reject -> downgrade to unresolved. Returns results."""
    verifier = verifier or StubVerifier()
    ledger = ledger or CostLedger()
    results: list[VerifyResult] = []
    for op in operations:
        if not needs_verify(op, sample_rate=sample_rate, rng=rng):
            continue
        res = verifier.verify(op, source)
        # StubVerifier records nothing itself; account for it here (cost 0 for the stub).
        if res.model == "stub":
            ledger.record(model="stub", stage="verify", input_tokens=0, output_tokens=0,
                          est_cost_usd=0.0, cache_hit=False)
        if res.verdict == "reject":
            op.operation = "unresolved"
            op.note = f"verifier rejected: {res.notes}"
        results.append(res)
    return results
