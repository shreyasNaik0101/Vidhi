// Natural-language Ask. Extract entity + date (+ optional clause) from a plain
// question, then filter to that entity and date and keyword-rank the clauses within
// that slice (Postgres full-text). No model at query time — hostable, fast, and it
// reinforces "filter before you retrieve". If who/when is missing, it asks.
import { loadClauseVersions } from './queries.js';
import { resolve } from './resolve.js';

// Order matters: more specific phrases first.
const ENTITY_ALIASES = [
  ['RCB', ['rural co-operative', 'rural cooperative', 'rcb']],
  ['UCB', ['urban co-operative', 'urban cooperative', 'ucb']],
  ['RRB', ['regional rural', 'rural bank', 'rrb']],
  ['LAB', ['local area', 'lab']],
  ['SFB', ['small finance', 'sfb']],
  ['SCB', ['commercial bank', 'scheduled commercial', 'scb']],
  ['NBFC', ['nbfc', 'non-banking', 'non banking']],
  ['AIFI', ['all india financial', 'aifi']],
  ['PB', ['payments bank', 'payment bank']],
  ['HFC', ['housing finance', 'hfc']],
  ['ARC', ['asset reconstruction', 'arc']],
];

const MONTHS = {
  jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6,
  jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12,
};

const iso = (y, m, d) => `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;

export function extractEntity(q) {
  const s = q.toLowerCase();
  for (const [code, aliases] of ENTITY_ALIASES) {
    if (aliases.some((a) => s.includes(a))) return code;
  }
  return null;
}

const MON = (w) => MONTHS[w.slice(0, 3)];

export function extractDate(q) {
  const s = q.toLowerCase();
  let m;
  if (/\b(today|now|currently|right now|at present|as of today|present)\b/.test(s))
    return new Date().toISOString().slice(0, 10);
  if ((m = s.match(/\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b/)))              // 2026-10-01 or 2026/10/1
    return iso(+m[1], +m[2], +m[3]);
  if ((m = s.match(/\b([a-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b/)) && MON(m[1]))
    return iso(+m[3], MON(m[1]), +m[2]);                                   // Month DD[th], YYYY
  if ((m = s.match(/\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3,9})\s+(\d{4})\b/)) && MON(m[2]))
    return iso(+m[3], MON(m[2]), +m[1]);                                   // DD[th] [of] Month YYYY
  if ((m = s.match(/\b([a-z]{3,9})\s+(\d{4})\b/)) && MON(m[1]))
    return iso(+m[2], MON(m[1]), 1);                                       // Month YYYY -> 1st
  return null;
}

export function extractClause(q) {
  // "clause 68C" / "para 68C" / bare "68C" (case-insensitive)
  const m = q.match(/\b(?:clause|para(?:graph)?)\s+(\d{1,3}[A-Za-z]?)\b/i)
    || q.match(/\b(\d{2,3}[A-Za-z])\b/);
  return m ? m[1].toUpperCase() : null;
}

// Which clause is the question about? Keyword-rank within the entity's clauses.
async function bestClause(pool, { mdFamily, entityCode, question }) {
  const { rows } = await pool.query(
    `SELECT c.clause_number,
            max(ts_rank(to_tsvector('english', c.text), plainto_tsquery('english', $3))) AS rank
     FROM clause c JOIN entity_type e ON e.id = c.entity_type_id
     WHERE c.md_family = $1 AND e.code = $2
     GROUP BY c.clause_number
     ORDER BY rank DESC
     LIMIT 1`,
    [mdFamily, entityCode, question],
  );
  return rows.length && Number(rows[0].rank) > 0 ? rows[0].clause_number : null;
}

export async function ask(pool, { question, family = 'IRACP' }) {
  const entity = extractEntity(question);
  if (!entity) {
    return {
      need: 'entity', question,
      message: 'Which type of entity is this about? For example a Regional Rural Bank, a Local Area Bank, or a Small Finance Bank.',
    };
  }
  const asOf = extractDate(question);
  if (!asOf) {
    return {
      need: 'date', question, entity,
      message: 'As of what date? Regulations take effect on a later date than they are published, so the answer depends on when you are asking.',
    };
  }

  let clause = extractClause(question);
  if (!clause) clause = await bestClause(pool, { mdFamily: family, entityCode: entity, question });
  if (!clause) {
    return {
      interpreted: { entity, family, asOf, clause: null },
      answer: { status: 'no_provision', clauseNumber: null, entityCode: entity, asOf, text: null,
                note: `Nothing on that topic is on record for ${entity}.` },
    };
  }

  const versions = await loadClauseVersions(pool, { mdFamily: family, entityCode: entity, clauseNumber: clause });
  const answer = resolve(versions, { mdFamily: family, entityCode: entity, clauseNumber: clause, asOf });
  return { interpreted: { entity, family, asOf, clause }, answer };
}
