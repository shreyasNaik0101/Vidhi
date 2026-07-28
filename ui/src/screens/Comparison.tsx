import { useEffect, useState } from 'react';
import { api, type CompareResult, type GoldenScenario } from '../api';
import { formatDate } from '../dates';
import { StatusBadge } from '../components/StatusBadge';

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
            <span><b>Entity</b> {picked.entity}</span>
            <span><b>Clause</b> <span className="chip">{picked.clause}</span></span>
            <span><b>As of</b> {formatDate(picked.asOf)}</span>
          </div>
        )}
      </div>

      {error && <div className="error">{error} — is the API + naive index built? (make db-sync · make eval-index · make api-dev)</div>}
      {loading && <div className="skeleton">Embedding the question and retrieving…</div>}

      {result && !loading && (
        <div className="grid-2">
          <FullPanel result={result} />
          <NaivePanel result={result} />
        </div>
      )}
    </div>
  );
}

function FullPanel({ result }: { result: CompareResult }) {
  const { full } = result;
  const correct = full.status === 'in_force';
  return (
    <div className="card card-pad cmp">
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
    <div className="card card-pad cmp">
      <div className="cmp-head">
        <div className="cmp-title">Normal AI search <span className="cmp-sub">nearest match</span></div>
        <span className={`badge ${anyError ? 'bad' : 'neutral'}`}>
          <span className="dot" />{anyError ? 'Wrong' : 'Answered'}
        </span>
      </div>
      <p className="clause-text naive">{naive.text}</p>
      <div className="err-list">
        {naive.errors.entity && (
          <span className="err-chip">Wrong entity — retrieved <b>{naive.answerEntity}</b>, asked <b>{scenario.entity}</b></span>
        )}
        {naive.errors.temporal && (
          <span className="err-chip">Not yet in force — text effective {formatDate(naive.effectiveDate)}, asked as of {formatDate(scenario.asOf)}</span>
        )}
        {naive.errors.shouldAbstain && (
          <span className="err-chip">Should have abstained — no provision is in force here</span>
        )}
        {!anyError && <span className="cmp-verdict good">No error on this scenario.</span>}
      </div>
      <div className="cmp-verdict bad">Ignores entity and date; retrieves by similarity alone, and cannot abstain.</div>
    </div>
  );
}
