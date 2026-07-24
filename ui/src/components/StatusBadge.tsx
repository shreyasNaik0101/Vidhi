import type { Status } from '../api';

const META: Record<Status, { cls: string; label: string }> = {
  in_force: { cls: 'now', label: 'In force' },
  not_yet_in_force: { cls: 'future', label: 'Not yet in force' },
  no_longer_in_force: { cls: 'neutral', label: 'No longer in force' },
  no_provision: { cls: 'neutral', label: 'No provision' },
};

export function StatusBadge({ status }: { status: Status }) {
  const m = META[status];
  return (
    <span className={`badge ${m.cls}`}>
      <span className="dot" />
      {m.label}
    </span>
  );
}
