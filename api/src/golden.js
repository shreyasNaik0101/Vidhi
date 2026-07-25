// Load golden questions that make good comparison scenarios (those with a concrete
// entity + clause + as_of, so both baselines can be run head-to-head).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const GOLDEN_PATH = path.resolve(__dirname, '..', '..', 'data', 'golden', 'questions.jsonl');

const COMPARABLE = new Set(['lookup', 'temporal_trap', 'entity_trap', 'non_existent']);

export function loadComparableGolden() {
  const text = fs.readFileSync(GOLDEN_PATH, 'utf-8');
  const out = [];
  for (const line of text.split('\n')) {
    const t = line.trim();
    if (!t || t.startsWith('//')) continue;
    const q = JSON.parse(t);
    if (!COMPARABLE.has(q.category) || !q.clause || !q.as_of) continue;
    out.push({
      id: q.id,
      category: q.category,
      question: q.question,
      entity: q.entity_type,
      family: q.md_family || 'IRACP',
      clause: q.clause,
      asOf: q.as_of,
      expectedStatus: q.expected_status,
      note: q.note || '',
    });
  }
  return out;
}
