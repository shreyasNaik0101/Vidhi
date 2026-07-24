// ISO-date helpers. We work in UTC and keep everything as 'YYYY-MM-DD' strings so
// the browser's local timezone never shifts a date across a boundary.

export function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export function toEpochDay(iso: string): number {
  return Math.floor(Date.parse(iso + 'T00:00:00Z') / 86_400_000);
}

export function fromEpochDay(day: number): string {
  return new Date(day * 86_400_000).toISOString().slice(0, 10);
}

export function addDays(iso: string, n: number): string {
  return fromEpochDay(toEpochDay(iso) + n);
}

export function clampDate(iso: string, lo: string, hi: string): string {
  if (iso < lo) return lo;
  if (iso > hi) return hi;
  return iso;
}

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/** '2026-10-01' -> 'Oct 1, 2026' */
export function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-').map(Number);
  return `${MONTHS[m - 1]} ${d}, ${y}`;
}

/** '2026-10-01' -> 'Oct 2026' */
export function formatMonth(iso: string): string {
  const [y, m] = iso.split('-').map(Number);
  return `${MONTHS[m - 1]} ${y}`;
}
