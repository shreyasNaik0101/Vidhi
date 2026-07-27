import { useRef, useState } from 'react';
import { api, type Resolution } from '../api';
import { formatDate } from '../dates';
import { StatusBadge } from '../components/StatusBadge';

// The Python ingestion service (CORS-enabled). Called directly; not via the Vite proxy.
const INGEST = 'http://localhost:8030';

// One streamed pipeline event.
interface Stage {
  stage: string;
  [k: string]: unknown;
}

export function Ingest() {
  const [text, setText] = useState('');
  const [stages, setStages] = useState<Stage[]>([]);
  const [running, setRunning] = useState(false);
  const [answer, setAnswer] = useState<Resolution | null>(null);
  const effectiveRef = useRef<string | null>(null);
  // Streamed events are queued and revealed one at a time, so checkpoints land with
  // a steady rhythm instead of arriving in bursts.
  const queue = useRef<Stage[]>([]);
  const draining = useRef(false);

  function drain() {
    if (draining.current) return;
    draining.current = true;
    const step = () => {
      const next = queue.current.shift();
      if (!next) { draining.current = false; return; }
      setStages((s) => [...s, next]);
      if (next.stage === 'classify') effectiveRef.current = (next.effective as string) ?? null;
      if (next.stage === 'persist' && next.query) void closeLoop(next.query as QueryHint);
      if (next.stage === 'done' || next.stage === 'error') setRunning(false);
      window.setTimeout(step, next.stage === 'start' ? 220 : 480);
    };
    step();
  }

  async function loadExample() {
    const r = await fetch(`${INGEST}/example`).then((x) => x.json());
    setText(r.text || '');
  }

  async function ingest() {
    setStages([]);
    setAnswer(null);
    setRunning(true);
    effectiveRef.current = null;
    queue.current = [];
    try {
      const res = await fetch(`${INGEST}/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, persist: true }),
      });
      if (!res.body) throw new Error('no stream');
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';
        for (const line of lines) {
          if (line.trim()) { queue.current.push(JSON.parse(line) as Stage); drain(); }
        }
      }
    } catch (err) {
      queue.current.push({ stage: 'error', message: String((err as Error).message) });
      drain();
    }
  }

  interface QueryHint { entity: string; family: string; clause: string; }
  async function closeLoop(q: QueryHint) {
    // prove it's live: query the clause we just ingested, at a date it's in force
    const asOf = effectiveRef.current || '2026-11-01';
    const r = await api.resolve(q.entity, q.clause, asOf, q.family);
    setAnswer(r);
  }

  return (
    <div className="stack">
      <div className="card card-pad">
        <p className="hint" style={{ marginBottom: 12 }}>
          Paste an RBI amendment and watch the pipeline run <b>live</b> — extract → classify →
          the AI parses it into structured clauses → it&rsquo;s saved and instantly queryable.
          Nothing here is hardcoded.
        </p>
        <textarea
          className="ingest-box"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste the text of an RBI amendment here…"
          rows={7}
        />
        <div className="ingest-actions">
          <button className="step-btn" onClick={loadExample} disabled={running}>Load example</button>
          <button className="btn-primary" onClick={ingest} disabled={running || !text.trim()}>
            {running ? 'Processing…' : 'Ingest ▸'}
          </button>
        </div>
      </div>

      {stages.length > 0 && (
        <div className="card card-pad">
          <div className="section-label" style={{ marginBottom: 12 }}>Pipeline (live)</div>
          <div className="pipe">
            {stages.map((s, i) => <StageRow key={i} s={s} running={running} last={i === stages.length - 1} />)}
          </div>
        </div>
      )}

      {answer && (
        <div className="card card-pad resolution">
          <div className="res-head">
            <div className="res-title">
              Just ingested → queried live: {answer.entityCode} clause <span className="cn">{answer.clauseNumber}</span>
            </div>
            <StatusBadge status={answer.status} />
          </div>
          {answer.status === 'in_force'
            ? <p className="clause-text">{answer.text}</p>
            : <p className="res-abstain">{answer.note}</p>}
        </div>
      )}
    </div>
  );
}

function StageRow({ s, running, last }: { s: Stage; running: boolean; last: boolean }) {
  const spinning = s.stage === 'parsing' && running && last;
  return (
    <div className={`pipe-row ${s.stage === 'error' ? 'err' : ''}`}>
      <span className={`pipe-dot ${spinning ? 'spin' : ''} ${s.stage}`} />
      <div className="pipe-body">
        <div className="pipe-name">{label(s.stage)}</div>
        <div className="pipe-detail">{detail(s)}</div>
      </div>
    </div>
  );
}

const NAMES: Record<string, string> = {
  start: 'Received', extract: 'Extract + normalise', classify: 'Classify',
  parsing: 'Parsing with local AI…', parse: 'Parsed structure', apply: 'Materialise timeline',
  persist: 'Saved to database', done: 'Done', error: 'Error',
  unrecognised: 'Not an amendment',
};
const label = (st: string) => NAMES[st] ?? st;

function detail(s: Stage) {
  switch (s.stage) {
    case 'extract':
      return <code className="pipe-pre">{String(s.preview)}…</code>;
    case 'classify':
      return (
        <span className="pipe-chips">
          <span className="chip">{String(s.entity)}</span>
          <span className="chip">{String(s.family)}</span>
          <span className="chip">{String(s.rbi_ref)}</span>
          <span>issued {formatDate(s.issued as string)} · effective {formatDate(s.effective as string)}</span>
          <span className="pipe-tag">via {String(s.method)}</span>
        </span>
      );
    case 'parsing':
      return <span>{String(s.message)}</span>;
    case 'parse':
      return (
        <div className="ops">
          {(s.operations as Op[]).map((o, i) => (
            <div key={i} className="op">
              <b>{o.operation}</b> into {o.chapter ? `Chapter ${o.chapter}` : 'document'}
              {o.section ? ` · ${o.section}` : ''} — clauses{' '}
              {o.clauses.map((c) => <span key={c.number} className="chip">{c.number}</span>)}
              <span className="pipe-tag">conf {o.confidence}</span>
            </div>
          ))}
        </div>
      );
    case 'apply':
      return <span>{(s.clauses as { clause: string; valid_from: string }[])
        .map((c) => `${c.clause} (from ${c.valid_from})`).join(', ')}</span>;
    case 'persist':
      return s.skipped
        ? <span>{String(s.skipped)}</span>
        : <span>{String(s.clauses)} clause(s) saved — querying it now…</span>;
    case 'error':
      return <span>{String(s.message)}</span>;
    default:
      return <span>{String(s.message ?? '')}</span>;
  }
}

interface Op {
  operation: string; chapter: string | null; section: string | null;
  confidence: number; clauses: { number: string; text: string }[];
}
