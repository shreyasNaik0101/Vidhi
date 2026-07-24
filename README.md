# RBI Regulatory Timeline Engine

Answers one question correctly that generic RAG gets wrong:

> **For a given type of regulated entity, on a given date, what does clause X actually say?**

The system filters on **entity type** and **temporal validity** *before* it does anything
semantic. See [`CLAUDE.md`](CLAUDE.md) for the full spec.

## Quick start

```bash
make install      # package + dev deps (Python 3.11+)
make db-up        # Postgres 16 + pgvector in Docker (port 5433)
make test         # run the suite
make extract      # extract + normalise the two sample PDFs
make cost         # LLM spend by stage/model (enforced under $20)
```

## Status — Week 1

| Area | State |
|---|---|
| Repo scaffold, `docker-compose`, schema, seed, Makefile | done |
| LLM plumbing: response cache, cost ledger + spend cap, router, pricing | done |
| Extract + normalise (all 5 documented PDF quirks) | done, 18 tests green |
| **Recon:** 16 Jul 2026 batch size | done — **16 docs** (8 IRACP inserts + 8 RSA parents) across **8 entity types** |
| **Recon:** a `substitute`-type amendment | found — Financial Statements Seventh Amendment 2026 (RBI/2026-27/35) |
| fetch / classify / parse / verify / apply / group | not started |
| Golden set, eval, UI, AWS | not started |

## Layout

See `CLAUDE.md §4`. Code under `src/rbi/`, tests under `tests/`, the two verified
sample PDFs under `data/samples/` (committed), raw downloads under `data/raw/` (gitignored).

## Cost discipline

Every model call goes through `src/rbi/llm/` — a SQLite response cache and a cost ledger
that **refuses** a paid call which would breach `MAX_SPEND_USD` (default $15). Local models
(`gemma3:4b`, `qwen3:8b`) are free; Bedrock is used only by the verifier agent.
