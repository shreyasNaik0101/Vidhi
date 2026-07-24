import { useEffect, useState } from 'react';
import { api, type ClauseOption, type Entity, type TimelineVersion } from '../api';
import { formatDate } from '../dates';

const FAMILY = 'IRACP';

export function ClauseTimeline() {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [entity, setEntity] = useState('RRB');
  const [clauses, setClauses] = useState<ClauseOption[]>([]);
  const [clause, setClause] = useState('68C');
  const [versions, setVersions] = useState<TimelineVersion[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { api.entities().then(setEntities).catch((e) => setError(String(e.message))); }, []);

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

  useEffect(() => {
    if (!clause) return;
    let live = true;
    api.timeline(FAMILY, entity, clause)
      .then((v) => { if (live) setVersions(v); })
      .catch((e) => { if (live) setError(String(e.message)); });
    return () => { live = false; };
  }, [entity, clause]);

  return (
    <div className="stack">
      <div className="card card-pad">
        <div className="controls">
          <div className="field entity">
            <label htmlFor="tl-entity">Regulated entity</label>
            <select id="tl-entity" value={entity} onChange={(e) => setEntity(e.target.value)}>
              {entities.map((e) => <option key={e.code} value={e.code}>{e.name} ({e.code})</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="tl-clause">Clause</label>
            <select id="tl-clause" value={clause} onChange={(e) => setClause(e.target.value)}>
              {clauses.length === 0 && <option value={clause}>{clause}</option>}
              {clauses.map((c) => <option key={c.clauseNumber} value={c.clauseNumber}>{c.clauseNumber}</option>)}
            </select>
          </div>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="card card-pad">
        <div className="section-label" style={{ marginBottom: 14 }}>
          Version history · {entity} clause {clause}
        </div>
        {!versions ? (
          <div className="skeleton">Loading…</div>
        ) : versions.length === 0 ? (
          <div className="hint">No versions for this clause.</div>
        ) : (
          <div className="tl">
            {versions.map((v, i) => {
              const open = v.validTo === null;
              return (
                <div className="tl-row" key={i}>
                  <div className="tl-rail">
                    <span className={`tl-node ${open ? '' : 'closed'}`} />
                    {i < versions.length - 1 && <span className="tl-line" />}
                  </div>
                  <div className="tl-body">
                    <div className="tl-range">
                      {formatDate(v.validFrom)} → {open ? <span className="open">present</span> : formatDate(v.validTo)}
                    </div>
                    <div className="tl-src">
                      created by <span className="chip">{v.createdBy ?? '—'}</span>
                      {v.supersededBy && <> · closed by <span className="chip">{v.supersededBy}</span></>}
                    </div>
                    <p className="clause-text">{v.text}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
