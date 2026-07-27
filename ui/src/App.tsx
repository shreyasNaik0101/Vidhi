import { useEffect, useState } from 'react';
import { AsOfExplorer } from './screens/AsOfExplorer';
import { ChangeFeed } from './screens/ChangeFeed';
import { ClauseTimeline } from './screens/ClauseTimeline';
import { Comparison } from './screens/Comparison';
import { Ingest } from './screens/Ingest';
import { Ask } from './screens/Ask';

type Tab = 'ask' | 'explorer' | 'changes' | 'timeline' | 'comparison' | 'ingest';

const TABS: { id: Tab; label: string; blurb: string }[] = [
  { id: 'ask', label: 'Ask',
    blurb: 'Type a question in plain English — it works out the bank and the date, and returns the exact rule.' },
  { id: 'explorer', label: 'Explore by date',
    blurb: 'Pick a bank and a clause, then drag the date. Watch the answer change as rules come into force.' },
  { id: 'changes', label: 'Change feed',
    blurb: 'One policy, many banks: the same rule lands at a different clause number for each bank type.' },
  { id: 'timeline', label: 'Clause history',
    blurb: 'Every version of a clause over time, with the amendment that created or replaced each one.' },
  { id: 'comparison', label: 'vs. Normal AI',
    blurb: 'The same question through normal AI search and through this system — see where normal AI picks the wrong bank.' },
  { id: 'ingest', label: 'Add a document',
    blurb: 'Paste a real amendment and watch it get read, structured, and made searchable — live.' },
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
  const [tab, setTab] = useState<Tab>('ask');
  const { effective, toggle } = useTheme();
  const active = TABS.find((t) => t.id === tab)!;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden><span /></div>
          <div>
            <h1>RBI Regulatory Timeline</h1>
            <p>The right rule, for the right bank, on the right date.</p>
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

      <p className="view-intro" key={active.id}>{active.blurb}</p>

      <main>
        {tab === 'ask' && <Ask />}
        {tab === 'explorer' && <AsOfExplorer />}
        {tab === 'changes' && <ChangeFeed />}
        {tab === 'timeline' && <ClauseTimeline />}
        {tab === 'comparison' && <Comparison />}
        {tab === 'ingest' && <Ingest />}
      </main>
    </div>
  );
}
