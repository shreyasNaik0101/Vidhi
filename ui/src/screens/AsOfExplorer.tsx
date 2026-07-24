import { useEffect, useMemo, useRef, useState } from 'react';
import { api, type ClauseOption, type Entity, type Resolution } from '../api';
import { addDays, formatDate, today } from '../dates';
import { TimeRibbon } from '../components/TimeRibbon';
import { StatusBadge } from '../components/StatusBadge';

const FAMILY = 'IRACP';

export function AsOfExplorer() {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [entity, setEntity] = useState('RRB');
  const [clauses, setClauses] = useState<ClauseOption[]>([]);
  const [clause, setClause] = useState('68C');
  const [asOf, setAsOf] = useState(today());
  const [res, setRes] = useState<Resolution | null>(null);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);

  useEffect(() => {
    api.entities().then(setEntities).catch((e) => setError(String(e.message)));
  }, []);

  // entity -> load its clause list, snap the selection to the first clause
  useEffect(() => {
    let live = true;
    api.clauses(entity, FAMILY).then((cs) => {
      if (!live) return;
      setClauses(cs);
      if (cs.length && !cs.some((c) => c.clauseNumber === clause)) setClause(cs[0].clauseNumber);
    }).catch((e) => setError(String(e.message)));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entity]);

  // resolve whenever entity / clause / date changes (stale-guarded)
  useEffect(() => {
    if (!clause) return;
    const id = ++seq.current;
    setError(null);
    api.resolve(entity, clause, asOf, FAMILY)
      .then((r) => { if (id === seq.current) setRes(r); })
      .catch((e) => { if (id === seq.current) setError(String(e.message)); });
  }, [entity, clause, asOf]);

  // ribbon domain is stable per clause (issued/effective don't move with as_of)
  const domain = useMemo(() => {
    const c = res?.candidates?.[0];
    const issued = c?.issuedDate ?? res?.issuedDate ?? null;
    const effective = c?.validFrom ?? res?.effectiveDate ?? res?.validFrom ?? null;
    if (issued && effective) {
      return { issued, effective, min: addDays(issued, -45), max: addDays(effective, 120) };
    }
    return { issued, effective, min: addDays(today(), -180), max: addDays(today(), 180) };
  }, [res]);

  return (
    <div className="stack">
      <div className="card card-pad">
        <div className="controls">
          <div className="field entity">
            <label htmlFor="entity">Regulated entity</label>
            <select id="entity" value={entity} onChange={(e) => setEntity(e.target.value)}>
              {entities.map((e) => (
                <option key={e.code} value={e.code}>{e.name} ({e.code})</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="clause">Clause</label>
            <select id="clause" value={clause} onChange={(e) => setClause(e.target.value)}>
              {clauses.length === 0 && <option value={clause}>{clause}</option>}
              {clauses.map((c) => (
                <option key={c.clauseNumber} value={c.clauseNumber}>
                  {c.clauseNumber}{c.chapter ? ` · Ch ${c.chapter}` : ''}
                </option>
              ))}
            </select>
          </div>
          <div className="field wide">
            <label htmlFor="asof">As of date</label>
            <div className="stepper">
              <button className="step-btn" onClick={() => setAsOf(addDays(asOf, -1))} aria-label="Previous day">−1d</button>
              <input id="asof" type="date" value={asOf} min={domain.min} max={domain.max}
                onChange={(e) => e.target.value && setAsOf(e.target.value)} />
              <button className="step-btn" onClick={() => setAsOf(addDays(asOf, 1))} aria-label="Next day">+1d</button>
              <button className="step-btn today" onClick={() => setAsOf(today())}>Today</button>
            </div>
          </div>
        </div>

        <div style={{ marginTop: 16 }}>
          <TimeRibbon
            value={asOf}
            min={domain.min}
            max={domain.max}
            issued={domain.issued}
            effective={domain.effective}
            onChange={setAsOf}
          />
        </div>
      </div>

      {error && <div className="error">{error} — is the API running on :3001? (make db-up · make db-sync · make api-dev)</div>}

      {res && <Resolution res={res} />}
    </div>
  );
}

function Resolution({ res }: { res: Resolution }) {
  const inForce = res.status === 'in_force';
  const issued = res.candidates?.[0]?.issuedDate ?? res.issuedDate ?? null;
  const effective = res.candidates?.[0]?.validFrom ?? res.effectiveDate ?? res.validFrom ?? null;
  const src = res.sourceRef ?? res.candidates?.[0]?.sourceRef ?? null;

  return (
    <div className="card card-pad resolution">
      <div className="res-head">
        <div className="res-title">
          {res.entityCode} · {res.mdFamily} · clause <span className="cn">{res.clauseNumber}</span>
          <span className="hint" style={{ marginLeft: 10 }}>as of {formatDate(res.asOf)}</span>
        </div>
        <StatusBadge status={res.status} />
      </div>

      {inForce ? (
        <p className="clause-text">{res.text}</p>
      ) : (
        <p className="res-abstain">
          {res.note}
          {res.status === 'no_provision' && (
            <> The system abstains rather than return another entity&rsquo;s or another era&rsquo;s text.</>
          )}
        </p>
      )}

      <div className="res-meta">
        {issued && <span><b>Issued</b> {formatDate(issued)}</span>}
        {effective && <span><b>Effective</b> {formatDate(effective)}</span>}
        {inForce && <span><b>Valid</b> {formatDate(res.validFrom)} → {res.validTo ? formatDate(res.validTo) : 'present'}</span>}
        {src && <span><b>Source</b> <span className="chip">{src}</span></span>}
      </div>

      {!inForce && res.candidates.length > 0 && (
        <div>
          <div className="section-label" style={{ marginBottom: 8 }}>Candidates considered</div>
          <div className="candidates">
            {res.candidates.map((c, i) => (
              <div className="candidate" key={i}>
                <span className="rng">{formatDate(c.validFrom)} → {c.validTo ? formatDate(c.validTo) : 'present'}</span>
                <span className="txt">{c.text}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
