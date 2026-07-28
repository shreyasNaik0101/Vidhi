import { useEffect, useState } from 'react';
import { api, type ChangeGroup } from '../api';
import { formatDate } from '../dates';

export function ChangeFeed() {
  const [groups, setGroups] = useState<ChangeGroup[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.changes().then(setGroups).catch((e) => setError(String(e.message)));
  }, []);

  if (error) return <div className="error">{error} — is the API running on :3001?</div>;
  if (!groups) return <div className="skeleton">Loading change feed…</div>;
  if (groups.length === 0) return <div className="hint">No change groups yet. Run <code>make db-sync</code>.</div>;

  return (
    <div className="feed">
      {groups.map((g) => (
        <div key={g.id} className="card card-pad change-group">
          <div className="cg-head">
            <div className="cg-title">{g.label}</div>
            <div className="cg-dates">
              Issued {formatDate(g.issuedDate)} · Effective {formatDate(g.effectiveDate)}
            </div>
          </div>
          <div className="fanout">
            {g.members.map((m) => (
              <div className="fan-row" key={m.entityCode + m.rbiRef}>
                <span className="fan-entity">{m.entityCode}</span>
                <span className="fan-loc">
                  {m.sectionHeading && <span className="chip">{m.sectionHeading}</span>}
                  <span className="chip">{m.rbiRef}</span>
                </span>
                {m.similarity !== null && <span className="sim">{m.similarity.toFixed(3)}</span>}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
