import { useEffect, useRef, useState } from 'react';
import { api, type AskResult } from '../api';
import { formatDate } from '../dates';
import { StatusBadge } from '../components/StatusBadge';

interface Turn { q: string; result: AskResult }

const STARTERS = [
  'How is accrued interest on an SNFA treated for a Regional Rural Bank in November 2026?',
  'What does a Local Area Bank do with SNFA income in December 2026?',
  'SNFA income rule for a rural bank in September 2026',
];

// quick-fill chips shown when the assistant asks for the missing piece
const ENTITY_CHIPS = [
  ['a Regional Rural Bank', 'RRB'], ['a Local Area Bank', 'LAB'], ['a Small Finance Bank', 'SFB'],
] as const;
const DATE_CHIPS = ['in September 2026', 'in November 2026', 'today'];

export function Ask() {
  const [input, setInput] = useState('');
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [turns, busy]);

  async function submit(q: string) {
    const question = q.trim();
    if (!question || busy) return;
    setInput('');
    setBusy(true);
    try {
      const result = await api.ask(question);
      setTurns((t) => [...t, { q: question, result }]);
    } catch (e) {
      setTurns((t) => [...t, { q: question, result: { message: `Error: ${(e as Error).message}` } }]);
    } finally {
      setBusy(false);
    }
  }

  // append a quick-fill to the most recent question and re-ask
  const refine = (add: string) => {
    const last = turns[turns.length - 1]?.q ?? '';
    submit(`${last} ${add}`);
  };

  return (
    <div className="stack">
      {turns.length === 0 && (
        <div className="hero">
          <h2 className="hero-title">Ask about a banking rule — in plain English.</h2>
          <p className="hero-sub">
            The same rule can have a different answer depending on <b>which bank</b> and <b>which date</b> —
            rules are often published months before they take effect. Ask a question and it works out both,
            returns the exact wording, or honestly says a rule isn&rsquo;t in force yet.
          </p>
          <div className="hero-try">Try one:</div>
          <div className="starters">
            {STARTERS.map((s) => (
              <button key={s} className="starter" onClick={() => submit(s)}>{s}</button>
            ))}
          </div>
        </div>
      )}

      {turns.length > 0 && (
        <div className="card card-pad chat">
          {turns.map((t, i) => (
            <div key={i} className="exchange">
              <div className="bubble user">{t.q}</div>
              <BotBubble result={t.result} onRefine={refine} last={i === turns.length - 1 && !busy} />
            </div>
          ))}
          {busy && <div className="bubble bot muted">Thinking…</div>}
          <div ref={endRef} />
        </div>
      )}

      <div className="card card-pad ask-bar">
        <input
          className="ask-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit(input)}
          placeholder="Ask about a clause… e.g. 'SNFA income for a rural bank in November 2026'"
        />
        <button className="btn-primary" onClick={() => submit(input)} disabled={busy || !input.trim()}>
          Ask
        </button>
      </div>
    </div>
  );
}

function BotBubble({ result, onRefine, last }: {
  result: AskResult; onRefine: (add: string) => void; last: boolean;
}) {
  // the assistant is asking for the missing piece
  if (result.need) {
    const chips = result.need === 'entity' ? ENTITY_CHIPS.map(([label]) => label) : DATE_CHIPS;
    return (
      <div className="bubble bot">
        <div>{result.message}</div>
        {last && (
          <div className="chip-row">
            {chips.map((c) => (
              <button key={c} className="fill-chip" onClick={() => onRefine(result.need === 'entity' ? `for ${c}` : c)}>
                {c}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (result.message) return <div className="bubble bot">{result.message}</div>;

  const a = result.answer;
  const it = result.interpreted;
  if (!a) return <div className="bubble bot">Sorry, I couldn&rsquo;t work that out.</div>;

  return (
    <div className="bubble bot">
      {it && (
        <div className="read-as">
          Read as: <b>{it.entity}</b>
          {it.clause && <> · clause <span className="chip">{it.clause}</span></>}
          {' '}· as of {formatDate(it.asOf)}
        </div>
      )}
      <div className="answer-line">
        <StatusBadge status={a.status} />
      </div>
      {a.status === 'in_force'
        ? <p className="clause-text">{a.text}</p>
        : <p className="res-abstain">{a.note}</p>}
    </div>
  );
}
