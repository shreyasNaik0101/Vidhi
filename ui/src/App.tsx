import { useEffect, useState } from 'react';
import { AsOfExplorer } from './screens/AsOfExplorer';
import { ChangeFeed } from './screens/ChangeFeed';
import { ClauseTimeline } from './screens/ClauseTimeline';
import { Comparison } from './screens/Comparison';
import { Ingest } from './screens/Ingest';

type Tab = 'explorer' | 'changes' | 'timeline' | 'comparison' | 'ingest';

const TABS: { id: Tab; label: string }[] = [
  { id: 'explorer', label: 'As-of explorer' },
  { id: 'changes', label: 'Change feed' },
  { id: 'timeline', label: 'Clause timeline' },
  { id: 'comparison', label: 'Naive RAG vs full' },
  { id: 'ingest', label: 'Ingest (live)' },
];

function useTheme() {
  const [theme, setTheme] = useState<'light' | 'dark' | null>(
    () => (localStorage.getItem('rbi-theme') as 'light' | 'dark') || null,
  );
  useEffect(() => {
    const root = document.documentElement;
    if (theme) root.setAttribute('data-theme', theme);
    else root.removeAttribute('data-theme');
    if (theme) localStorage.setItem('rbi-theme', theme);
  }, [theme]);
  const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches;
  const effective = theme ?? (prefersDark ? 'dark' : 'light');
  return { effective, toggle: () => setTheme(effective === 'dark' ? 'light' : 'dark') };
}

export function App() {
  const [tab, setTab] = useState<Tab>('explorer');
  const { effective, toggle } = useTheme();

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden />
          <div>
            <h1>RBI Regulatory Timeline</h1>
            <p>What does a clause say, for this entity, on this date?</p>
          </div>
        </div>
        <button className="icon-btn" onClick={toggle} aria-label="Toggle colour theme" title="Toggle theme">
          {effective === 'dark' ? '☀' : '☾'}
        </button>
      </header>

      <nav className="nav" aria-label="Views">
        {TABS.map((t) => (
          <button key={t.id} aria-current={tab === t.id} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>

      <main>
        {tab === 'explorer' && <AsOfExplorer />}
        {tab === 'changes' && <ChangeFeed />}
        {tab === 'timeline' && <ClauseTimeline />}
        {tab === 'comparison' && <Comparison />}
        {tab === 'ingest' && <Ingest />}
      </main>
    </div>
  );
}
