import { useCallback, useRef } from 'react';
import { addDays, clampDate, formatDate, formatMonth, fromEpochDay, toEpochDay } from '../dates';

interface Props {
  value: string;        // as_of
  min: string;
  max: string;
  issued: string | null;
  effective: string | null;
  onChange: (iso: string) => void;
}

/** The persistent time ribbon — the spatial spine of the UI. Dragging the handle
 *  across the effective-date line visibly flips the answer (in force vs not yet). */
export function TimeRibbon({ value, min, max, issued, effective, onChange }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);
  const lo = toEpochDay(min);
  const hi = toEpochDay(max);
  const span = Math.max(1, hi - lo);

  const pct = (iso: string) => ((toEpochDay(iso) - lo) / span) * 100;
  const clampPct = (iso: string) => Math.min(100, Math.max(0, pct(iso)));

  const setFromClientX = useCallback(
    (clientX: number) => {
      const el = trackRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const frac = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
      onChange(clampDate(fromEpochDay(Math.round(lo + frac * span)), min, max));
    },
    [lo, span, min, max, onChange],
  );

  const onPointerDown = (e: React.PointerEvent) => {
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    setFromClientX(e.clientX);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (e.buttons === 1) setFromClientX(e.clientX);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    const step: Record<string, number> = {
      ArrowLeft: -1, ArrowRight: 1, ArrowDown: -1, ArrowUp: 1, PageDown: -30, PageUp: 30,
    };
    if (e.key in step) {
      e.preventDefault();
      onChange(clampDate(addDays(value, step[e.key]), min, max));
    } else if (e.key === 'Home') {
      e.preventDefault(); onChange(min);
    } else if (e.key === 'End') {
      e.preventDefault(); onChange(max);
    }
  };

  const effPct = effective ? pct(effective) : null;

  return (
    <div className="ribbon-wrap">
      <div
        className="ribbon"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
      >
        <div className="ribbon-track" ref={trackRef}>
          {effPct !== null && (
            <div className="ribbon-inforce" style={{ left: `${effPct}%`, right: 0 }} />
          )}
        </div>

        {effPct !== null && <div className="ribbon-eff-line" style={{ left: `${effPct}%` }} />}

        {issued && <div className="ribbon-marker issued" style={{ left: `${pct(issued)}%` }} />}
        {effective && <div className="ribbon-marker effective" style={{ left: `${effPct}%` }} />}

        {issued && (
          <div className="ribbon-tick" style={{ left: `${pct(issued)}%` }}>
            Issued<span className="sub">{formatMonth(issued)}</span>
          </div>
        )}
        {effective && (
          <div className="ribbon-tick" style={{ left: `${effPct}%` }}>
            In force<span className="sub">{formatMonth(effective)}</span>
          </div>
        )}

        <div
          className="ribbon-handle"
          style={{ left: `${clampPct(value)}%` }}
          role="slider"
          tabIndex={0}
          aria-label="As-of date"
          aria-valuetext={formatDate(value)}
          aria-valuemin={0}
          aria-valuemax={span}
          aria-valuenow={toEpochDay(value) - lo}
          onKeyDown={onKeyDown}
        >
          <span className="ribbon-flag">{formatDate(value)}</span>
        </div>
      </div>

      <div className="ribbon-legend">
        <span><i style={{ background: 'var(--future)' }} /> Not yet in force</span>
        <span><i style={{ background: 'var(--now)' }} /> In force</span>
        <span className="hint">Drag the handle, or focus it and use ← → (±1 day), PgUp/PgDn (±30).</span>
      </div>
    </div>
  );
}
