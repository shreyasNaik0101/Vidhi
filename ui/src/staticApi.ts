// Static-mode API. On the always-on GitHub Pages demo there is no backend, so the
// read endpoints are served from a baked dataset (api/scripts/export-static.mjs) and
// the two dynamic inputs — arbitrary as-of dates and free-text questions — run their
// logic client-side. resolve() and the Ask extractors are direct ports of the Node
// API (api/src/resolve.js, api/src/ask.js), kept behaviourally identical so the
// hosted demo answers exactly as the live stack does.
import dataset from './staticData/dataset.json';
import type {
  Entity,
  ClauseOption,
  Version,
  Resolution,
  ChangeGroup,
  TimelineVersion,
  GoldenScenario,
  CompareResult,
  AskResult,
} from './api';

interface Dataset {
  entities: Entity[];
  families: string[];
  clausesByEntity: Record<string, Record<string, ClauseOption[]>>;
  timelines: Record<string, TimelineVersion[]>;
  clauseVersions: Version[];
  changes: ChangeGroup[];
  golden: GoldenScenario[];
  compare: Record<string, CompareResult>;
}

const data = dataset as unknown as Dataset;
const ready = <T>(v: T): Promise<T> => Promise.resolve(v);

// --- resolve(): port of api/src/resolve.js ------------------------------------
function resolve(
  versions: Version[],
  { mdFamily, entityCode, clauseNumber, asOf }:
    { mdFamily: string; entityCode: string; clauseNumber: string; asOf: string },
): Resolution {
  const candidates = versions
    .filter((v) => v.mdFamily === mdFamily && v.entityCode === entityCode && v.clauseNumber === clauseNumber)
    .sort((a, b) => (a.validFrom < b.validFrom ? -1 : a.validFrom > b.validFrom ? 1 : 0));

  const base = { mdFamily, entityCode, clauseNumber, asOf, candidates };

  if (candidates.length === 0) {
    return { ...base, status: 'no_provision', text: null, validFrom: null, validTo: null,
      effectiveDate: null, note: `clause ${clauseNumber} does not exist for ${entityCode}` };
  }

  for (const v of candidates) {
    if (v.validFrom <= asOf && (v.validTo === null || v.validTo > asOf)) {
      return { ...base, status: 'in_force', text: v.text, validFrom: v.validFrom, validTo: v.validTo,
        effectiveDate: null, note: null, sourceRef: v.sourceRef ?? null, issuedDate: v.issuedDate ?? null };
    }
  }

  const future = candidates.filter((v) => v.validFrom > asOf);
  if (future.length > 0) {
    const soonest = future.reduce((a, b) => (a.validFrom < b.validFrom ? a : b));
    return { ...base, status: 'not_yet_in_force', text: null, validFrom: null, validTo: null,
      effectiveDate: soonest.validFrom,
      note: `clause ${clauseNumber} was issued but comes into force ${soonest.validFrom}; ` +
            `on ${asOf} the prior text (if any) applies` };
  }

  const latest = candidates.reduce((a, b) => (a.validFrom > b.validFrom ? a : b));
  return { ...base, status: 'no_longer_in_force', text: null, validFrom: null, validTo: latest.validTo,
    effectiveDate: null, note: `clause ${clauseNumber} was closed on ${latest.validTo}` };
}

// --- Ask extractors: port of api/src/ask.js -----------------------------------
const ENTITY_ALIASES: [string, string[]][] = [
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
const MONTHS: Record<string, number> = {
  jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12,
};
const iso = (y: number, m: number, d: number) =>
  `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
const MON = (w: string) => MONTHS[w.slice(0, 3)];

function extractEntity(q: string): string | null {
  const s = q.toLowerCase();
  for (const [code, aliases] of ENTITY_ALIASES) if (aliases.some((a) => s.includes(a))) return code;
  return null;
}

function extractDate(q: string): string | null {
  const s = q.toLowerCase();
  let m: RegExpMatchArray | null;
  if (/\b(today|now|currently|right now|at present|as of today|present)\b/.test(s))
    return new Date().toISOString().slice(0, 10);
  if ((m = s.match(/\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b/)))
    return iso(+m[1], +m[2], +m[3]);
  if ((m = s.match(/\b([a-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b/)) && MON(m[1]))
    return iso(+m[3], MON(m[1]), +m[2]);
  if ((m = s.match(/\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([a-z]{3,9})\s+(\d{4})\b/)) && MON(m[2]))
    return iso(+m[3], MON(m[2]), +m[1]);
  if ((m = s.match(/\b([a-z]{3,9})\s+(\d{4})\b/)) && MON(m[1]))
    return iso(+m[2], MON(m[1]), 1);
  return null;
}

function extractClause(q: string): string | null {
  const m = q.match(/\b(?:clause|para(?:graph)?)\s+(\d{1,3}[A-Za-z]?)\b/i)
    || q.match(/\b(\d{2,3}[A-Za-z])\b/);
  return m ? m[1].toUpperCase() : null;
}

// Keyword-rank a question against an entity's clause texts — the client-side stand-in
// for the Postgres full-text ranking in api/src/ask.js (bestClause).
const STOP = new Set(['the', 'and', 'for', 'are', 'was', 'that', 'this', 'with', 'from',
  'what', 'when', 'does', 'has', 'have', 'not', 'any', 'such', 'been', 'shall', 'which',
  'where', 'who', 'how', 'a', 'an', 'of', 'to', 'in', 'on', 'is', 'it', 'as', 'at', 'by']);
const tokens = (s: string) =>
  s.toLowerCase().match(/[a-z0-9]+/g)?.filter((w) => w.length >= 3 && !STOP.has(w)) ?? [];

function bestClause(family: string, entity: string, question: string): string | null {
  const qset = new Set(tokens(question));
  if (qset.size === 0) return null;
  const scores = new Map<string, number>();
  for (const v of data.clauseVersions) {
    if (v.mdFamily !== family || v.entityCode !== entity) continue;
    const ctoks = tokens(v.text);
    let score = 0;
    for (const t of ctoks) if (qset.has(t)) score += 1;
    scores.set(v.clauseNumber, Math.max(scores.get(v.clauseNumber) ?? 0, score));
  }
  let best: string | null = null;
  let bestScore = 0;
  for (const [cn, sc] of scores) if (sc > bestScore) { bestScore = sc; best = cn; }
  return bestScore > 0 ? best : null;
}

function ask(question: string, family = 'IRACP'): AskResult {
  const entity = extractEntity(question);
  if (!entity) {
    return { need: 'entity', question,
      message: 'Which type of entity is this about? For example a Regional Rural Bank, a Local Area Bank, or a Small Finance Bank.' } as AskResult;
  }
  const asOf = extractDate(question);
  if (!asOf) {
    return { need: 'date', question, entity,
      message: 'As of what date? Regulations take effect on a later date than they are published, so the answer depends on when you are asking.' } as AskResult;
  }
  let clause = extractClause(question);
  if (!clause) clause = bestClause(family, entity, question);
  if (!clause) {
    return {
      interpreted: { entity, family, asOf, clause: null },
      answer: { status: 'no_provision', clauseNumber: '', entityCode: entity, mdFamily: family, asOf,
        text: null, validFrom: null, validTo: null, effectiveDate: null, candidates: [],
        note: `Nothing on that topic is on record for ${entity}.` },
    } as AskResult;
  }
  const answer = resolve(data.clauseVersions, { mdFamily: family, entityCode: entity, clauseNumber: clause, asOf });
  return { interpreted: { entity, family, asOf, clause }, answer };
}

// --- the api surface, matching ./api ------------------------------------------
export const staticApi = {
  entities: () => ready<Entity[]>(data.entities),
  clauses: (entity: string, family = 'IRACP') =>
    ready<ClauseOption[]>(data.clausesByEntity[family]?.[entity] ?? []),
  resolve: (entity: string, clause: string, asOf: string, family = 'IRACP') =>
    ready<Resolution>(resolve(data.clauseVersions, { mdFamily: family, entityCode: entity, clauseNumber: clause, asOf })),
  changes: () => ready<ChangeGroup[]>(data.changes),
  timeline: (family: string, entity: string, clause: string) =>
    ready<TimelineVersion[]>(data.timelines[`${family}/${entity}/${clause}`] ?? []),
  golden: () => ready<GoldenScenario[]>(data.golden),
  ask: (q: string, family = 'IRACP') => ready<AskResult>(ask(q, family)),
  compare: (s: GoldenScenario) => {
    const hit = data.compare[s.id];
    if (hit) return ready<CompareResult>(hit);
    // fallback: resolve the full-system answer; no naive baseline off-dataset
    const full = resolve(data.clauseVersions, { mdFamily: s.family, entityCode: s.entity, clauseNumber: s.clause, asOf: s.asOf });
    return ready<CompareResult>({ scenario: { entity: s.entity, family: s.family, clause: s.clause, asOf: s.asOf, question: s.question }, full, naive: null });
  },
};
