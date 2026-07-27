-- RBI Regulatory Timeline Engine — schema (PROJECT_SPEC.md §5)
-- Postgres 16 + pgvector. Runs at container init.

CREATE EXTENSION IF NOT EXISTS vector;

-- The 11 categories from the 2025 consolidation (only 8 got the 16 Jul SNFA change).
CREATE TABLE IF NOT EXISTS entity_type (
    id          SERIAL PRIMARY KEY,
    code        TEXT UNIQUE NOT NULL,   -- 'RRB', 'LAB', 'SCB', 'UCB', 'NBFC', ...
    name        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document (
    id              SERIAL PRIMARY KEY,
    rbi_ref         TEXT UNIQUE NOT NULL,        -- 'RBI/2026-27/201'
    dor_ref         TEXT,                        -- 'DOR.STR.REC.166/21-04-048/2026-27'
    title           TEXT NOT NULL,
    doc_type        TEXT NOT NULL,               -- 'master_direction' | 'amendment' | 'circular'
    md_family       TEXT,                        -- 'IRACP', 'RSA', 'KYC', ...
    entity_type_id  INT REFERENCES entity_type(id),
    issued_date     DATE NOT NULL,
    effective_date  DATE,                        -- NULL means same as issued_date
    source_url      TEXT NOT NULL,
    sha256          TEXT NOT NULL,
    raw_text        TEXT NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per operation an amendment performs. An amendment may perform several.
CREATE TABLE IF NOT EXISTS amendment_op (
    id                  SERIAL PRIMARY KEY,
    amendment_doc_id    INT NOT NULL REFERENCES document(id),
    seq                 INT NOT NULL,            -- (i), (ii), (iii) in the source
    operation           TEXT NOT NULL,           -- 'insert' | 'substitute' | 'omit' | 'unresolved'
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
CREATE TABLE IF NOT EXISTS clause (
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

CREATE INDEX IF NOT EXISTS clause_lookup_idx
    ON clause (md_family, entity_type_id, clause_number, valid_from);
CREATE INDEX IF NOT EXISTS clause_embedding_idx
    ON clause USING hnsw (embedding vector_cosine_ops);

-- Links the same substantive change across entity types.
CREATE TABLE IF NOT EXISTS change_group (
    id              SERIAL PRIMARY KEY,
    label           TEXT NOT NULL,       -- 'SNFA income recognition'
    issued_date     DATE NOT NULL,
    effective_date  DATE
);

CREATE TABLE IF NOT EXISTS change_group_member (
    change_group_id INT REFERENCES change_group(id),
    amendment_op_id INT REFERENCES amendment_op(id),
    similarity      NUMERIC(4,3),
    PRIMARY KEY (change_group_id, amendment_op_id)
);
