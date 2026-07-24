// Express read API over the RBI clause timeline.
import express from 'express';
import cors from 'cors';
import { pool, ping } from './db.js';
import { resolve } from './resolve.js';
import {
  listEntities,
  loadClauseVersions,
  listClauses,
  clauseTimeline,
  changeFeed,
} from './queries.js';

const app = express();
app.use(cors());
app.use(express.json());

const wrap = (fn) => (req, res) =>
  fn(req, res).catch((err) => {
    console.error(err);
    res.status(500).json({ error: 'internal_error', detail: String(err.message || err) });
  });

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

app.get('/api/health', wrap(async (_req, res) => {
  res.json({ ok: await ping() });
}));

app.get('/api/entities', wrap(async (_req, res) => {
  res.json(await listEntities(pool));
}));

// GET /api/clauses?entity=RRB&family=IRACP  -> clause numbers available (UI picker)
app.get('/api/clauses', wrap(async (req, res) => {
  const { entity, family = 'IRACP' } = req.query;
  if (!entity) return res.status(400).json({ error: 'entity is required' });
  res.json(await listClauses(pool, { mdFamily: family, entityCode: entity }));
}));

// GET /api/resolve?entity=RRB&family=IRACP&clause=68C&as_of=2026-10-02  -> the date flip
app.get('/api/resolve', wrap(async (req, res) => {
  const { entity, family = 'IRACP', clause, as_of: asOf } = req.query;
  if (!entity || !clause || !asOf) {
    return res.status(400).json({ error: 'entity, clause and as_of are required' });
  }
  if (!ISO_DATE.test(asOf)) {
    return res.status(400).json({ error: 'as_of must be YYYY-MM-DD' });
  }
  const versions = await loadClauseVersions(pool, {
    mdFamily: family, entityCode: entity, clauseNumber: clause,
  });
  res.json(resolve(versions, { mdFamily: family, entityCode: entity, clauseNumber: clause, asOf }));
}));

// GET /api/clauses/:family/:entity/:clause/timeline  -> every version of one clause
app.get('/api/clauses/:family/:entity/:clause/timeline', wrap(async (req, res) => {
  const { family, entity, clause } = req.params;
  res.json(await clauseTimeline(pool, { mdFamily: family, entityCode: entity, clauseNumber: clause }));
}));

// GET /api/changes  -> change feed (entity fan-out per substantive change)
app.get('/api/changes', wrap(async (_req, res) => {
  res.json(await changeFeed(pool));
}));

const PORT = Number(process.env.API_PORT) || 3001;
// Only listen when run directly (not when imported by tests).
if (process.argv[1] && process.argv[1].endsWith('server.js')) {
  app.listen(PORT, () => console.log(`RBI timeline API on http://localhost:${PORT}`));
}

export { app };
