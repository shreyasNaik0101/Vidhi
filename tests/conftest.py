"""Test isolation: point every DB-touching test at a dedicated `rbi_test` database.

The dev database (`rbi`) holds the demo data. The integration tests TRUNCATE and
re-insert, so they must never run against it. Setting DATABASE_URL here — before any
`rbi.*` module imports the config — routes all DB access to `rbi_test`, which this
session provisions with the schema and seeds. If Postgres is unavailable, DB tests
skip themselves as before.
"""
import os
from pathlib import Path

# MUST run before rbi.config is imported. python-dotenv's load_dotenv() does not
# override an already-set env var, so this wins over .env.
_ADMIN_URL = "postgresql://rbi:rbi@127.0.0.1:5433/rbi"
_TEST_URL = "postgresql://rbi:rbi@127.0.0.1:5433/rbi_test"
os.environ["DATABASE_URL"] = _TEST_URL

def _provision() -> None:
    import psycopg

    with psycopg.connect(_ADMIN_URL, autocommit=True, connect_timeout=3) as admin:
        with admin.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = 'rbi_test'")
            if not cur.fetchone():
                cur.execute("CREATE DATABASE rbi_test")

    root = Path(__file__).resolve().parents[1]
    schema = (root / "src" / "rbi" / "db" / "schema.sql").read_text(encoding="utf-8")
    seed = (root / "src" / "rbi" / "db" / "seed.sql").read_text(encoding="utf-8")
    with psycopg.connect(_TEST_URL, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(schema)   # CREATE ... IF NOT EXISTS -> idempotent
        cur.execute(seed)     # ON CONFLICT DO NOTHING -> idempotent


# Provision at import (before collection) so any collection-time skipif that probes
# the DB sees rbi_test already there. Skips silently if Postgres is unavailable.
try:
    _provision()
except Exception:
    pass
