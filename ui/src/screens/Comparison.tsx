import { useEffect, useState } from 'react';
import { api, type CompareResult, type GoldenScenario } from '../api';
import { formatDate } from '../dates';
import { StatusBadge } from '../components/StatusBadge';

// Headline result, measured on the 48-question golden set (`make eval`).
const SCORE = [
  { label: 'Answered correctly', naive: '4.2%', full: '68.8%' },
  { label: 'Answered for the wrong bank', naive: '47.9%', full: '0%' },
  { label: 'Used an out-of-date rule', naive: '16.7%', full: '0%' },
];

export function Comparison() {
  const [scenarios, setScenarios] = useState<GoldenScenario[]>([]);
  const [picked, setPicked] = useState<GoldenScenario | null>(null);
  const [result, setResult] = useState<CompareResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.golden().then((s) => {
      setScenarios(s);
      if (s.length) setPicked(s[0]);
    }).catch((e) => setError(String(e.message)));
  }, []);

  useEffect(() => {
    if (!picked) return;
    setLoading(true);
    setError(null);
    api.compare(picked)
      .then(setResult)
      .catch((e) => setError(String(e.message)))
      .finally(() => setLoading(false));
  }, [picked]);

  return (
    <div className="stack">
      <ScoreBoard />

      <div className="card card-pad">
        <div className="field">
          <label htmlFor="scenario">Pick a question to test</label>
          <select
            id="scenario"
            value={picked?.id ?? ''}
            onChange={(e) => setPicked(scenarios.find((s) => s.id === e.target.value) ?? null)}
          >
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                [{s.category}] {s.entity} {s.clause} · {s.question.slice(0, 70)}
              </option>
            ))}
          </select>
        </div>
        {picked && (
          <div className="res-meta" style={{ marginTop: 12 }}>
            <span><b>Bank</b> {picked.entity}</span>
            <span><b>Clause</b> <span className="chip">{picked.clause}</span></span>
            <span><b>As of</b> {formatDate(picked.asOf)}</span>
          </div>
        )}
      </div>

      {error && <div className="error">{error} — is the API + naive index built? (make db-sync · make eval-index · make api-dev)</div>}
      {loading && <div className="skeleton">Embedding the question and retrieving…</div>}

      {result && !loading && (
        <>
          <VerdictBanner result={result} />
          <div className="grid-2">
            <FullPanel result={result} />
            <NaivePanel result={result} />
          </div>
        </>
      )}
    </div>
  );
}

function ScoreBoard() {
  return (
    <div className="card card-pad scoreboard">
      <div className="sb-caption">
        <span className="section-label">Across a 48-question test set</span>
        <span className="sb-repro">reproduce with <code>make eval</code></span>
      </div>
      <div className="sb">
        <div className="sb-row sb-head">
          <span />
          <span className="sb-col naive">Normal AI</span>
          <span className="sb-col full">This system</span>
        </div>
        {SCORE.map((s) => (
          <div className="sb-row" key={s.label}>
            <span className="sb-metric">{s.label}</span>
            <span className="sb-val naive">{s.naive}</span>
            <span className="sb-val full">{s.full}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function VerdictBanner({ result }: { result: CompareResult }) {
  const naive = result.naive;
  const reasons: string[] = [];
  if (naive?.errors.entity) reasons.push('answered for the wrong bank');
  if (naive?.errors.temporal) reasons.push('used a rule that isn’t in force yet');
  if (naive?.errors.shouldAbstain) reasons.push('answered when it should have said “no rule applies”');
  const naiveWrong = reasons.length > 0;

  return (
    <div className={`verdict-banner ${naiveWrong ? 'win' : 'tie'}`}>
      <span className="vb-badge" aria-hidden>{naiveWrong ? '✓' : '≈'}</span>
      {naiveWrong ? (
        <span><b>This system got it right.</b> Normal AI {reasons.join('; ')}.</span>
      ) : (
        <span><b>Both answered correctly here.</b> Try a “trap” scenario (wrong-bank or out-of-date) to see where normal AI breaks.</span>
      )}
    </div>
  );
}

function FullPanel({ result }: { result: CompareResult }) {
  const { full } = result;
  const correct = full.status === 'in_force';
  return (
    <div className="card card-pad cmp win">
      <div className="cmp-head">
        <div className="cmp-title">This system</div>
        <StatusBadge status={full.status} />
      </div>
      {correct ? (
        <p className="clause-text">{full.text}</p>
      ) : (
        <p className="res-abstain">{full.note}</p>
      )}
      <div className="cmp-verdict good">✓ Correct — knows the bank and the date, and abstains when nothing is in force.</div>
    </div>
  );
}

function NaivePanel({ result }: { result: CompareResult }) {
  const { naive, scenario } = result;
  if (!naive) return (
    <div className="card card-pad cmp">
      <div className="cmp-head"><div className="cmp-title">Normal AI search</div></div>
      <div className="hint">No index. Run <code>make eval-index</code>.</div>
    </div>
  );
  const anyError = naive.errors.entity || naive.errors.temporal || naive.errors.shouldAbstain;
  return (
    <div className={`card card-pad cmp ${anyError ? 'lose' : ''}`}>
      <div className="cmp-head">
        <div className="cmp-title">Normal AI search <span className="cmp-sub">nearest match</span></div>
        <span className={`badge ${anyError ? 'bad' : 'neutral'}`}>
          <span className="dot" />{anyError ? 'Wrong' : 'Answered'}
        </span>
      </div>
      <p className="clause-text naive">{naive.text}</p>
      <div className="err-list">
        {naive.errors.entity && (
          <span className="err-chip">Wrong bank — retrieved <b>{naive.answerEntity}</b>, but the question is about <b>{scenario.entity}</b></span>
        )}
        {naive.errors.temporal && (
          <span className="err-chip">Not in force yet — this text takes effect {formatDate(naive.effectiveDate)}, asked as of {formatDate(scenario.asOf)}</span>
        )}
        {naive.errors.shouldAbstain && (
          <span className="err-chip">Should have said nothing — no rule is in force here</span>
        )}
        {!anyError && <span className="cmp-verdict good">No error on this scenario.</span>}
      </div>
      <div className="cmp-verdict bad">Matches on wording alone — ignores the bank and the date, and can’t say “no rule applies”.</div>
    </div>
  );
}
