// Bake the read API's responses into a static dataset for the always-on demo.
//
// Reuses the real query + resolver + naive-baseline logic against the live DB and
// Ollama, so the static export is byte-for-byte what the running API would return.
// The UI's static mode (ui/src/staticApi.ts) reads this file and runs resolve/ask
// client-side for the dynamic inputs (arbitrary as-of dates, free-text questions).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { pool } from '../src/db.js';
import {
  listEntities,
  loadClauseVersions,
  listClauses,
  clauseTimeline,
  changeFeed,
} from '../src/queries.js';
import { resolve } from '../src/resolve.js';
import { embedQuery, nearestChunk } from '../src/naive.js';
import { loadComparableGolden } from '../src/golden.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT_DIR = path.resolve(__dirname, '..', '..', 'ui', 'src', 'staticData');
const FAMILIES = ['IRACP'];

async function main() {
  const entities = await listEntities(pool);

  const clausesByEntity = {}; // family -> entity -> ClauseOption[]
  const timelines = {}; // "family/entity/clause" -> TimelineVersion[]
  const seen = new Set();
  const clauseVersions = []; // flat, deduped — the client-side resolver runs over this

  for (const fam of FAMILIES) {
    clausesByEntity[fam] = {};
    for (const e of entities) {
      const cls = await listClauses(pool, { mdFamily: fam, entityCode: e.code });
      if (!cls.length) continue;
      clausesByEntity[fam][e.code] = cls;
      for (const c of cls) {
        const key = `${fam}/${e.code}/${c.clauseNumber}`;
        timelines[key] = await clauseTimeline(pool, {
          mdFamily: fam, entityCode: e.code, clauseNumber: c.clauseNumber,
        });
        const versions = await loadClauseVersions(pool, {
          mdFamily: fam, entityCode: e.code, clauseNumber: c.clauseNumber,
        });
        for (const v of versions) {
          const vk = `${v.mdFamily}/${v.entityCode}/${v.clauseNumber}/${v.validFrom}`;
          if (!seen.has(vk)) { seen.add(vk); clauseVersions.push(v); }
        }
      }
    }
  }

  const changes = await changeFeed(pool);
  const golden = loadComparableGolden();

  // One head-to-head comparison per golden scenario (mirrors GET /api/compare).
  const compare = {};
  for (const s of golden) {
    const versions = await loadClauseVersions(pool, {
      mdFamily: s.family, entityCode: s.entity, clauseNumber: s.clause,
    });
    const full = resolve(versions, {
      mdFamily: s.family, entityCode: s.entity, clauseNumber: s.clause, asOf: s.asOf,
    });
    let naive = null;
    try {
      const chunk = await nearestChunk(pool, await embedQuery(s.question));
      naive = chunk
        ? {
            text: chunk.chunk_text,
            answerEntity: chunk.entity_code,
            effectiveDate: chunk.effective_date,
            issuedDate: chunk.issued_date,
            errors: {
              entity: Boolean(s.entity) && chunk.entity_code !== s.entity,
              temporal: Boolean(chunk.effective_date) && s.asOf < chunk.effective_date,
              shouldAbstain: full.status !== 'in_force',
            },
          }
        : null;
    } catch (err) {
      console.error(`  naive baseline failed for ${s.id}: ${err.message}`);
    }
    compare[s.id] = {
      scenario: { entity: s.entity, family: s.family, clause: s.clause, asOf: s.asOf, question: s.question },
      full,
      naive,
    };
  }

  const dataset = {
    generatedAt: new Date().toISOString(),
    families: FAMILIES,
    entities,
    clausesByEntity,
    timelines,
    clauseVersions,
    changes,
    golden,
    compare,
  };

  fs.mkdirSync(OUT_DIR, { recursive: true });
  const out = path.join(OUT_DIR, 'dataset.json');
  fs.writeFileSync(out, JSON.stringify(dataset, null, 2));
  console.log(
    `wrote ${out}\n  ${clauseVersions.length} clause versions · ${golden.length} golden scenarios ` +
    `· ${changes.length} change groups · ${Object.keys(compare).length} comparisons`,
  );
  await pool.end();
}

main().catch((err) => { console.error(err); process.exit(1); });
