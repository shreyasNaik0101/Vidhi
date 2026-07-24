# RBI Timeline API (Node + Express)

A thin **read** API over the clause timeline in Postgres. The Python pipeline fills
the database (`make db-sync`); this server only queries it.

> Stack note: the spec (CLAUDE.md §10) named FastAPI. We chose Node/Express by
> preference. The one piece of real logic — the as-of resolver — is **ported to JS
> and tested** (`test/resolve.test.js`), mirroring the Python `tests/test_apply.py`,
> so both languages agree on in-force / abstention decisions.

## Run

```bash
cd api
npm install
npm test          # vitest — the ported resolver
npm start         # http://localhost:3001  (needs Postgres up: make db-up && make db-sync)
```

Reads `DATABASE_URL` from the repo-root `.env` (defaults to
`postgresql://rbi:rbi@localhost:5433/rbi`). Port via `API_PORT` (default 3001).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | DB reachable? |
| GET | `/api/entities` | the 11 entity types |
| GET | `/api/clauses?entity=RRB&family=IRACP` | clause numbers available (UI picker) |
| GET | `/api/resolve?entity=RRB&family=IRACP&clause=68C&as_of=2026-10-02` | **the date flip** |
| GET | `/api/clauses/:family/:entity/:clause/timeline` | every version of one clause |
| GET | `/api/changes` | change feed — entity fan-out per substantive change |

`/api/resolve` returns the full resolution including `status`
(`in_force` / `not_yet_in_force` / `no_longer_in_force` / `no_provision`), the text
when in force, and `candidates` — so the UI can render an abstention as a
first-class result showing what was considered.
