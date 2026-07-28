// Build the canned ingest stream for static mode from the real example text +
// the baked RRB 68C clause, matching the FastAPI service's stage payloads exactly.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..', '..');
const SCRATCH = process.argv[2];

const dataset = JSON.parse(fs.readFileSync(path.join(root, 'ui/src/staticData/dataset.json'), 'utf8'));
const v = dataset.clauseVersions.find((x) => x.entityCode === 'RRB' && x.clauseNumber === '68C');
const example = fs.readFileSync(path.join(SCRATCH, 'rrb_example.txt'), 'utf8').trim();

const stream = [
  { stage: 'start', message: 'received amendment text' },
  { stage: 'extract', chars: example.length, preview: example.slice(0, 600) },
  { stage: 'classify', rbi_ref: 'RBI/2026-27/201', entity: 'RRB', family: 'IRACP',
    doc_type: 'amendment', method: 'regex', issued: '2026-07-16', effective: '2026-10-01', missing: [] },
  { stage: 'parsing', message: 'running gemma4:latest — this is the slow step' },
  { stage: 'parse', operations: [{ seq: 1, operation: 'insert', chapter: v.chapter,
    section: 'Prudential norms on income recognition', confidence: 0.96,
    evidence: 'the following clause 68C shall be inserted',
    clauses: [{ number: '68C', text: v.text }] }] },
  { stage: 'apply', clauses: [{ clause: '68C', valid_from: '2026-10-01' }] },
  { stage: 'persist', clauses: 1, query: { entity: 'RRB', family: 'IRACP', clause: '68C' } },
  { stage: 'done' },
];

const out = path.join(root, 'ui/src/staticData/ingest.json');
fs.writeFileSync(out, JSON.stringify({ example, stream }, null, 2));
console.log(`wrote ${out} — example ${example.length} chars, ${stream.length} stages, 68C ${v.text.length} chars`);
