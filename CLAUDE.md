# RBI Regulatory Timeline Engine — Project Spec

Paste this as `CLAUDE.md` in the repo root. It is the standing brief for the project.

---

## 1. What this is

A system that tracks amendments to RBI Master Directions and can answer one question correctly:

> **"For a given type of regulated entity, on a given date, what does clause X actually say?"**

Generic RAG cannot answer this. It dumps every document into one index and returns whatever is
semantically nearest, ignoring *who is asking* and *when*. This system filters on entity type and
temporal validity **before** it does anything semantic.

This is a portfolio project. It must be finished, measured, and demoable in 4 weeks. Scope
discipline beats feature count.

---

## 2. Verified ground truth

These facts are confirmed from real source PDFs. Do not re-derive them, and do not invent
figures beyond them.

**The 2025 consolidation.** On 28 Nov 2025, circular RBI/2025-26/100 withdrew 9,445 circulars and
replaced them with 244 entity-specific Master Directions covering 11 categories of regulated
entity. RBI stated the exercise was done on an "as-is" basis — no substantive change to
regulatory content. **Do not build any feature that assumes the consolidation changed
requirements.** The project is about amendments issued *after* consolidation.

**Two real amendments, both dated 16 July 2026, both in `data/samples/`:**

| | Doc A | Doc B |
|---|---|---|
| RBI ref | RBI/2026-27/201 | RBI/2026-27/202 |
| DOR ref | DOR.STR.REC.166/21-04-048/2026-27 | DOR.STR.REC.167/21-04-048/2026-27 |
| Entity type | Regional Rural Banks | Local Area Banks |
| Master Direction | IRACP | IRACP |
| Operation | insert into Chapter V | insert into Chapter V |
| Section heading | `B.` | `E1.` |
| Clauses added | `68C`, `68D` | `119C`, `119D` |
| Issued | 2026-07-16 | 2026-07-16 |
| **Effective** | **2026-10-01** | **2026-10-01** |

Four properties of this pair drive the whole design:

1. **Same policy, different coordinates.** Identical substance lands at `68C` for RRBs and `119C`
   for LABs. Entity type is not metadata garnish — it changes the answer.
2. **Near-identical text, not identical.** Word-level similarity is 0.957. The single difference:
   RRB says `a Specified Non-Financial Asset (SNFA),` where LAB says `an SNFA,`. Exact matching
   says "different", embeddings say "same" without explaining why. This is the case the verifier
   agent exists for.
3. **Issued ≠ effective.** Published 16 July, in force 1 October. Between those dates the *old*
   text is correct. A naive system ingesting the PDF today returns the wrong answer.
4. **Amendments cascade.** Both are "consequent to" a separate amendment issued the same day
   (Resolution of Stressed Assets Second Amendment Directions, 2026). One policy decision
   propagates across multiple Master Directions.

**Sequential numbering** (201/202, DOR 166/167) implies these shipped as a batch, with parallel
versions for other entity types. Confirming the batch size is a Week 1 task.

---

## 3. Hard constraints

- **Machine:** 16 GB RAM, no GPU. Do not propose anything needing a GPU.
- **Budget:** ~$125 AWS credits total, target spend **under $20**. Cost control is a functional
  requirement, not an afterthought.
- **Local models via Ollama:** `gemma3:4b` for extraction/classification, `qwen3:8b` for amendment
  parsing. Set `num_ctx` explicitly (4096 default) — do not rely on Ollama defaults.
- **Bedrock is for the verifier agent only.** It is the one paid inference step.
- **Timeline:** 4 weeks.

### Forbidden — these cause surprise bills or wasted weeks

- ❌ **OpenSearch Serverless** — minimum billed capacity, ~$170+/month idle. Use pgvector.
- ❌ **RDS** — no free tier available on this account. Postgres runs in Docker locally.
- ❌ **VPC with private subnets / NAT Gateway** — ~$32/month forever. Lambdas stay outside a VPC.
- ❌ **Any LLM call that bypasses the response cache.**
- ❌ **Running any stage on the full corpus before a `--limit` run has passed.**

---

## 4. Repo layout

```
rbi-timeline/
├── CLAUDE.md
├── Makefile                  # every stage has a target
├── docker-compose.yml        # postgres + pgvector only
├── pyproject.toml
├── .env.example
├── data/
│   ├── samples/              # the two verified PDFs, committed
│   ├── raw/                  # downloaded PDFs (gitignored)
│   └── golden/               # eval set (committed — this is precious)
├── src/rbi/
│   ├── config.py
│   ├── db/                   # schema.sql, migrations, queries
│   ├── fetch/                # RBI notification scraper
│   ├── extract/              # pymupdf + normalisation
│   ├── classify/             # doc type, entity types, dates
│   ├── parse/                # amendment → structured operation
│   ├── verify/               # Bedrock verifier agent
│   ├── apply/                # build the clause timeline
│   ├── group/                # link same change across entity types
│   ├── query/                # the as-of resolver + FastAPI
│   ├── llm/                  # cache, router, cost ledger
│   └── eval/                 # harness, baselines, metrics
├── infra/                    # AWS CDK (Python), minimal
├── ui/                       # React app
└── tests/
```

---

## 5. Data model

Postgres 16 + pgvector. Schema lives in `src/rbi/db/schema.sql`.

### Core tables

```sql
-- The 11 categories from the 2025 consolidation
CREATE TABLE entity_type (
    id          SERIAL PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,   -- 'RRB', 'LAB', 'SCB', 'UCB', 'NBFC', ...
    name        TEXT NOT NULL
);

CREATE TABLE document (
    id              SERIAL PRIMARY KEY,
    rbi_ref         TEXT UNIQUE NOT NULL,        -- 'RBI/2026-27/201'
    dor_ref         TEXT,                        -- 'DOR.STR.REC.166/21-04-048/2026-27'
    title           TEXT NOT NULL,
    doc_type        TEXT NOT NULL,               -- 'master_direction' | 'amendment' | 'circular'
    md_family       TEXT,                        -- 'IRACP', 'KYC', 'RSA', ...
    entity_type_id  INT REFERENCES entity_type(id),
    issued_date     DATE NOT NULL,
    effective_date  DATE,                        -- NULL means same as issued_date
    source_url      TEXT NOT NULL,
    sha256          TEXT NOT NULL,
    raw_text        TEXT NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per operation an amendment performs. An amendment may perform several.
CREATE TABLE amendment_op (
    id                  SERIAL PRIMARY KEY,
    amendment_doc_id    INT NOT NULL REFERENCES document(id),
    seq                 INT NOT NULL,            -- (i), (ii), (iii) in the source
    operation           TEXT NOT NULL,           -- 'insert' | 'substitute' | 'omit'
    target_md_family    TEXT NOT NULL,
    target_entity_type  INT REFERENCES entity_type(id),
    target_chapter      TEXT,                    -- 'V'
    target_anchor       TEXT,                    -- '68C' or NULL for chapter-level inserts
    section_heading     TEXT,                    -- 'B.' / 'E1.'
    new_text            TEXT,
    evidence_span       TEXT NOT NULL,           -- verbatim source sentence proving this parse
    parse_confidence    NUMERIC(3,2) NOT NULL,
    verified            BOOLEAN NOT NULL DEFAULT FALSE,
    verifier_notes      TEXT,
    status              TEXT NOT NULL DEFAULT 'parsed'  -- 'parsed'|'verified'|'unresolved'
);

-- The timeline. One row per (clause, version).
CREATE TABLE clause (
    id                  SERIAL PRIMARY KEY,
    md_family           TEXT NOT NULL,
    entity_type_id      INT NOT NULL REFERENCES entity_type(id),
    chapter             TEXT,
    clause_number       TEXT NOT NULL,           -- '68C'
    sort_key            TEXT NOT NULL,           -- zero-padded for ordering
    text                TEXT NOT NULL,
    valid_from          DATE NOT NULL,           -- = effective_date of creating amendment
    valid_to            DATE,                    -- NULL = currently in force
    created_by_op_id    INT REFERENCES amendment_op(id),
    superseded_by_op_id INT REFERENCES amendment_op(id),
    embedding           vector(384)
);

CREATE INDEX ON clause (md_family, entity_type_id, clause_number, valid_from);
CREATE INDEX ON clause USING hnsw (embedding vector_cosine_ops);

-- Links the same substantive change across entity types
CREATE TABLE change_group (
    id          SERIAL PRIMARY KEY,
    label       TEXT NOT NULL,       -- 'SNFA income recognition'
    issued_date DATE NOT NULL,
    effective_date DATE
);

CREATE TABLE change_group_member (
    change_group_id INT REFERENCES change_group(id),
    amendment_op_id INT REFERENCES amendment_op(id),
    similarity      NUMERIC(4,3),
    PRIMARY KEY (change_group_id, amendment_op_id)
);
```

### The query that defines the product

```sql
-- What does clause :clause say for entity :entity on date :as_of?
SELECT text, valid_from, valid_to
FROM clause
WHERE md_family = :family
  AND entity_type_id = :entity
  AND clause_number = :clause
  AND valid_from <= :as_of
  AND (valid_to IS NULL OR valid_to > :as_of);
```

Every retrieval path in the system applies the `entity_type_id` and validity filters **before**
vector search. Semantic similarity narrows within an already-correct slice; it never selects the
slice.

### Two dates, kept distinct

- `issued_date` — when RBI published it.
- `effective_date` — when it starts applying. `clause.valid_from` derives from this, **never**
  from `issued_date`.

If `effective_date` is in the future relative to the query's `as_of`, the amendment exists but is
not in force. The API must be able to say so explicitly — that is the demo.

---

## 6. Pipeline

Each stage is a separate CLI command with `--limit N` and `--dry-run`. Stages are idempotent and
resumable. `make pipeline` runs them in order.

| # | Stage | Tool | LLM? |
|---|---|---|---|
| 1 | `fetch` | requests + BeautifulSoup | no |
| 2 | `extract` | pymupdf | no |
| 3 | `normalise` | python | no |
| 4 | `classify` | regex first, gemma3:4b fallback | local |
| 5 | `parse` | qwen3:8b, strict JSON | local |
| 6 | `verify` | **Bedrock** | paid |
| 7 | `apply` | python | no |
| 8 | `group` | embeddings + qwen3:8b confirm | local |

### 6.1 fetch

Scrape the RBI notifications list (`rbi.org.in` → Notifications). Store PDF bytes to
`data/raw/`, compute sha256, skip anything already stored with a matching hash. Respect
`robots.txt`, one request per 2 seconds, real User-Agent, exponential backoff. Never re-download.

### 6.2 extract

`pymupdf` per page, concatenated. Verified quirks to handle — write a test for each using the two
sample PDFs:

- **Header/footer extracts before body.** The Mumbai address block appears first in reading order.
  Strip known boilerplate lines.
- **Devanagari is mojibake** (`įरज़वर्` not `रिज़र्व`) — broken font encoding, boilerplate only.
  Drop any line where >30% of characters fall in `\u0900-\u097F`.
- **Ligatures.** `Central Oﬃce` uses a single `ﬃ` glyph. Apply
  `unicodedata.normalize('NFKC', text)` on every extracted string.
- **Orphaned footnote markers.** Doc B emits a bare `2` on its own line. Drop lines that are a
  single digit and not followed by `.`.
- **Hard line wraps mid-sentence.** Reflow: join lines unless the next line starts a new clause
  (`^\d+[A-Z]?\.`), a new numbered para (`^\d+\.`), or a roman sub-item (`^\([ivx]+\)`).

### 6.3 classify

Regex first — it handles most of it and costs nothing:

- `RBI/\d{4}-\d{2}/\d+` → rbi_ref
- `DOR\.[A-Z]{3}\.[A-Z]{3}\.\d+/[\d-]+/\d{4}-\d{2}` → dor_ref
- Entity type from the title parenthetical: `Reserve Bank of India (Regional Rural Banks – ...)`
- `come into force with effect from (\w+ \d{1,2}, \d{4})` → effective_date
- Doc type from title: contains `Amendment Directions` → amendment

Fall back to `gemma3:4b` only when a regex misses. Log which path was used — the regex-hit rate
is a number worth reporting.

### 6.4 parse

The core local-LLM step. Input: one amendment's operative section. Output: strict JSON, one object
per operation.

```json
{
  "operations": [
    {
      "seq": 1,
      "operation": "insert",
      "target_chapter": "V",
      "target_anchor": null,
      "section_heading": "B.",
      "new_clauses": [
        {"clause_number": "68C", "text": "Any accrued but unrealised interest..."},
        {"clause_number": "68D", "text": "Any income received from an SNFA..."}
      ],
      "evidence_span": "The following shall be inserted in Chapter V – Income Recognition:",
      "confidence": 0.94
    }
  ]
}
```

Rules for the parser:

- `evidence_span` must be **verbatim** from the source. Validate with a substring check and reject
  the parse if it fails. This is a cheap, deterministic hallucination guard — use it everywhere.
- Support all three operations. You have `insert` samples only; find a `substitute` example in
  Week 1 and add it to `data/samples/`.
- **`unresolved` is a valid output.** If the anchor is ambiguous, emit `confidence < 0.5` and
  `operation: "unresolved"`. Never guess a target. The system's willingness to abstain is a
  headline feature.
- Ask for JSON only, no prose, no markdown fences. Strip fences defensively anyway.
- Keep output short — generation dominates CPU latency.

### 6.5 verify (Bedrock — the only paid step)

A second agent independently checks each parsed operation against the raw source text and must
either confirm with a quoted evidence span or downgrade to `unresolved`.

- Model: a cheap Bedrock model for clear cases, escalate only on disagreement.
- Route: only operations with `parse_confidence` between 0.5 and 0.9, plus a 10% random sample of
  high-confidence ones for calibration. High-confidence parses that pass a deterministic check
  skip Bedrock entirely.
- The verifier **cannot** invent a mapping. Its outputs are `confirm`, `correct` (with evidence),
  or `reject`.
- Record token counts and estimated cost per call in the ledger.

### 6.6 apply

Walk verified operations in `effective_date` order and materialise `clause` rows:

- `insert` → new clause row, `valid_from = effective_date`, `valid_to = NULL`
- `substitute` → close the prior row (`valid_to = effective_date`), insert the new one
- `omit` → close the prior row, insert nothing

Assert after every run: no clause has two rows with overlapping validity for the same
`(md_family, entity_type, clause_number)`. Fail loudly if violated.

### 6.7 group

Link the same substantive change across entity types. Embed each operation's `new_text`, cluster
within a single `issued_date`, confirm candidate pairs with the local model. Store the similarity
score — the 0.957 between the RRB and LAB SNFA clauses is your reference value.

---

## 7. LLM plumbing (`src/rbi/llm/`)

Build this **before** any stage that calls a model. It is what keeps the project under $20.

### Cache

SQLite at `data/llm_cache.db`. Key: `sha256(model + prompt + params)`. Check before every call,
no exceptions. Re-running the pipeline after a cache warm-up must cost approximately zero.

### Cost ledger

```sql
CREATE TABLE llm_call (
    id INTEGER PRIMARY KEY,
    ts TEXT, model TEXT, stage TEXT,
    input_tokens INT, output_tokens INT,
    est_cost_usd REAL, cache_hit BOOLEAN
);
```

Read `MAX_SPEND_USD` from env (default `15.00`). Before each paid call, sum spend to date; if the
call would exceed the cap, **raise and stop**. AWS will not protect you — this code must.

Add `make cost` to print spend by stage and by model.

### Router

`route(task, difficulty) -> model`. Escalation is explicit and logged, never implicit. Every
routing decision is recorded so the accuracy-vs-cost table can be built from real data.

**Bedrock pricing changes.** Read per-token rates from a config file, not hardcoded constants, and
verify them against the AWS pricing page before any bulk run.

---

## 8. AWS integration (manually triggered)

Real services, real IaC, no idle spend. AWS CDK in Python under `infra/`.

| Service | Use | Notes |
|---|---|---|
| **S3** | Raw PDFs + extracted text | Versioning on. Lifecycle to IA after 30 days. |
| **Bedrock** | Verifier agent | via boto3, `us-east-1` or nearest enabled region |
| **Lambda** | `fetch_notifications` | **No VPC.** Invoked manually via `make aws-fetch`. |
| **Step Functions** | Orchestrates extract → classify → parse → verify | Standard workflow, started manually via `make aws-run` |
| **CloudWatch Logs** | Structured JSON logs from every stage | 7-day retention to stay free |
| **AWS Budgets** | Alarms at $20 and $50 | **Create these before the first deploy.** |

Rules:

- No EventBridge schedule. A cron rule that fires while you sleep is how credits vanish. The
  scheduling code may exist but must be deployed **disabled**, with a comment saying why.
- Lambda outside any VPC. It only needs internet + S3 + Bedrock.
- Postgres stays local. The Step Functions workflow writes results to S3; a local `make aws-sync`
  pulls them into Postgres.
- Least-privilege IAM per function. No wildcard resource ARNs.
- `make aws-destroy` must fully tear down. Verify it works in Week 4 before you stop paying
  attention.

Step Functions gives you a visual execution graph with per-step timing and failure states — worth
a screenshot in the writeup.

---

## 9. Evaluation harness

This produces the numbers that make the project credible. Build it in Week 2, not Week 4.

### Golden set — `data/golden/questions.jsonl`

Target 60–100 questions, hand-written. Minimum 40 before any accuracy claim.

```json
{
  "id": "g001",
  "question": "How is accrued but unrealised interest on an acquired SNFA treated?",
  "entity_type": "RRB",
  "as_of": "2026-08-01",
  "expected_status": "not_yet_in_force",
  "expected_clause": null,
  "note": "Amendment issued 2026-07-16 but effective 2026-10-01"
}
```

Question categories — build all six, roughly evenly:

1. **Straight lookup** — clause in force, correct entity.
2. **Temporal trap** — `as_of` before `effective_date`. Expected: the old text, or "no provision".
3. **Entity trap** — ask an RRB question using LAB clause numbers. Expected: refusal or correction,
   never the LAB text.
4. **Cross-entity equivalence** — "what's the RRB equivalent of LAB clause 119C?" Expected: `68C`.
5. **Non-existent** — a clause that does not exist for that entity. Expected: abstention.
6. **Cascade** — "what else changed because of the RSA amendment?"

### Baselines

Run all three against the same golden set:

- **A — Naive RAG.** Every document chunked into one pgvector index. No entity filter, no date
  filter. This is what a normal project builds, and it is what you compare against.
- **B — Filtered retrieval.** Entity + date filters, no LLM parsing of amendments.
- **C — Full system.** Parsed operations, materialised timeline, verifier, abstention.

### Metrics — always report as a pair

| Metric | Definition |
|---|---|
| **Accuracy** | correct ÷ answered |
| **Coverage** | answered ÷ total |
| **Entity error rate** | answers citing the wrong entity's clause |
| **Temporal error rate** | answers using text not in force on `as_of` |
| **Cost per 100 questions** | from the ledger |

**Never report accuracy alone.** A system that abstains on everything scores 100% accuracy and is
useless. `make eval` must print accuracy and coverage together, and a coverage figure below 60%
should be flagged as degenerate.

Also produce the **accuracy-vs-cost table** across local / open-hosted / frontier / routed. This
is the single most valuable artifact in the repo.

---

## 10. React UI (`ui/`)

Vite + React + TypeScript. Backend API in `api/` (Node + Express).

> Deviation from the original brief (which named FastAPI): the backend is Node +
> Express by project preference. The pipeline stays in Python and fills Postgres
> (`make db-sync`); the API only reads. The one piece of real logic — the as-of
> resolver — is ported to JS and tested (`api/test/resolve.test.js`) so Python and
> JS agree. The document wins over the spec (§13); this note records the change.

### Design brief

Read `/mnt/skills/public/frontend-design/SKILL.md` before writing any UI code and follow its
process — brainstorm a token system, critique it against the defaults it warns about, then build.

Direction for this brief: the subject is **regulatory time**, so make time the spatial spine of
the interface. The signature element is a persistent horizontal time ribbon showing where the
selected `as_of` date sits relative to issue and effective dates — always visible, the thing the
whole UI orbits.

Do not reach for the broadsheet/hairline-rules treatment that regulatory subjects invite; the
skill flags it as an AI default. Avoid the cream-plus-serif-plus-terracotta palette and the
near-black-plus-acid-green palette for the same reason. Pick a palette where "in force" and "not
yet in force" are legible at a glance without relying on red/green alone.

### Screens

1. **As-of explorer** *(primary)* — entity-type selector + date control. Shows the clause text in
   force, a version badge, and validity dates. Moving the date across an effective date visibly
   changes the answer. This is the demo.
2. **Change feed** — amendments by issue date, each expandable to show the entity fan-out for the
   same substantive change.
3. **Clause timeline** — every version of one clause, with the amendment that created and closed
   each.
4. **Comparison view** — the same question answered by naive RAG (baseline A) and the full system,
   side by side, with the naive answer's error labelled.
5. **Eval dashboard** — accuracy and coverage per baseline, the accuracy-vs-cost table, and the
   distribution of abstentions.

### Non-negotiable UI behaviours

- Abstention renders as a **first-class result**, not an error state. Show confidence, show the
  candidates considered, show why none was selected.
- Every displayed clause carries its source document reference and effective date.
- The date control must default to today and be obviously draggable/steppable.
- Responsive to mobile, visible keyboard focus, `prefers-reduced-motion` respected.

---

## 11. Four-week plan

**Week 1 — foundations and one more check**
- Repo, docker-compose Postgres+pgvector, schema, Makefile.
- LLM cache + cost ledger **first**, before any model call.
- Extract pipeline with tests against both sample PDFs covering all five quirks.
- Ollama running, `gemma3:4b` and `qwen3:8b` pulled, `num_ctx` configured.
- **Two data tasks:** count how many entity-versions of the 16 July SNFA change RBI issued; find
  and commit one `substitute`-type amendment.
- UI shell with hardcoded data — the as-of explorer, faked. This pins the API contract.

**Week 2 — parsing and the golden set**
- Classify stage, regex-first, with hit-rate logging.
- Parse stage producing validated JSON with verbatim evidence spans.
- Apply stage building the clause timeline, with the overlap assertion.
- **Hand-write 40+ golden questions across all six categories.** Do not skip or defer this. Every
  number in Weeks 3 and 4 depends on it.
- Baseline A (naive RAG) built and scored — you need the thing you beat.

**Week 3 — verification and measurement**
- Bedrock verifier with strict confirm/correct/reject outputs.
- Router with logged escalation.
- Grouping across entity types.
- Full eval across baselines A, B, C. Produce the accuracy-vs-cost table.
- Wire the UI to the real API.

**Week 4 — AWS and polish**
- CDK deploy: S3, Lambda, Step Functions, CloudWatch. Budgets **first**.
- `make aws-run` end to end; screenshot the Step Functions execution graph.
- Comparison view and eval dashboard.
- README with architecture diagram, the accuracy-vs-cost table, and an honest limitations section.
- Verify `make aws-destroy` works.

---

## 12. Definition of done

Three things must exist. Everything else is optional.

1. **The date flip.** Same entity, same clause, two dates either side of 1 Oct 2026 — the answer
   visibly changes.
2. **The accuracy-vs-cost table.** Real measured numbers across models, including the routed
   system, with coverage reported alongside accuracy.
3. **The abstention.** A live case where the system says "I can't resolve this", shows its
   candidates and confidence, and refuses to guess.

---

## 13. Working agreements

- Every stage: `--limit` and `--dry-run`. Test on 5 documents before 500. Always.
- Prefer deterministic checks over model calls. The verbatim-substring validation on evidence
  spans catches more hallucination than any prompt instruction.
- `unresolved` is a success state. Code that cannot express uncertainty is a bug.
- Structured JSON logs everywhere, with stage, doc ref, model, and cache-hit status.
- Commit the golden set. Never regenerate it — it is hand-labelled ground truth.
- Secrets in `.env`, never committed. `.env.example` documents every key.
- When a source document contradicts this spec, the document wins. Update the spec and note it.
- The real RBI source text contains typos (`"in, in exercise"`, `modifies` vs `modify`). Do not
  normalise them away — matching must tolerate them.
