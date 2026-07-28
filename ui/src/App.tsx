import { useEffect, useState, type ReactNode } from 'react';
import { AsOfExplorer } from './screens/AsOfExplorer';
import { ChangeFeed } from './screens/ChangeFeed';
import { ClauseTimeline } from './screens/ClauseTimeline';
import { Comparison } from './screens/Comparison';
import { Ingest } from './screens/Ingest';
import { Ask } from './screens/Ask';

type Tab = 'ask' | 'explorer' | 'changes' | 'timeline' | 'comparison' | 'ingest';

interface TabDef {
  id: Tab;
  label: string;
  icon: ReactNode;
  title: string;
  blurb: string;
  steps?: string[];
}

// Small line icons (currentColor) so the nav is scannable at a glance.
const I = {
  ask: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
  explorer: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="17" rx="2" /><path d="M3 9h18M8 2v4M16 2v4" /><circle cx="12" cy="15" r="1.6" fill="currentColor" stroke="none" />
    </svg>
  ),
  changes: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3 3 8l9 5 9-5-9-5ZM3 13l9 5 9-5M3 18l9 5 9-5" />
    </svg>
  ),
  timeline: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" />
    </svg>
  ),
  comparison: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="7" height="16" rx="1.5" /><rect x="14" y="4" width="7" height="16" rx="1.5" />
    </svg>
  ),
  ingest: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3v5h5" /><path d="M19 8v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7Z" /><path d="M12 11v6M9 14h6" />
    </svg>
  ),
};

const TABS: TabDef[] = [
  {
    id: 'ask', label: 'Ask', icon: I.ask,
    title: 'Ask about a banking rule, in plain English',
    blurb: 'Type a question the way you’d say it aloud. It works out which bank and which date you mean, then shows the exact rule — or honestly says it isn’t in force yet.',
  },
  {
    id: 'explorer', label: 'Explore by date', icon: I.explorer,
    title: 'Watch a rule switch on',
    blurb: 'The same rule can be published months before it legally applies. Drag the date and watch the answer flip.',
    steps: ['Pick a bank type and a clause', 'Drag the blue handle along the date line', 'Watch the badge flip from “Not yet” to “In force”'],
  },
  {
    id: 'changes', label: 'Change feed', icon: I.changes,
    title: 'One policy, many banks',
    blurb: 'The same change often lands at a different clause number for each type of bank. Each card shows one change fanning out across banks — and the text-similarity that linked them.',
  },
  {
    id: 'timeline', label: 'Clause history', icon: I.timeline,
    title: 'Every version of a rule over time',
    blurb: 'See how one rule changed, and which amendment created or replaced each version.',
    steps: ['Pick a bank type and a clause', 'Read top to bottom — each entry is one version and when it applied'],
  },
  {
    id: 'comparison', label: 'vs. Normal AI', icon: I.comparison,
    title: 'This system vs. ordinary AI search',
    blurb: 'The same question, answered two ways. See where ordinary AI search grabs the wrong bank or an out-of-date rule — and where this system refuses to guess.',
    steps: ['Pick a scenario', 'Left = this system, right = normal AI search', 'Red flags mark where normal AI got it wrong'],
  },
  {
    id: 'ingest', label: 'Add a document', icon: I.ingest,
    title: 'Add a document, watch it become searchable',
    blurb: 'Paste a real RBI amendment and watch the pipeline read it, structure it, and make it queryable — step by step.',
    steps: ['Paste amendment text, or tap “Load example”', 'Watch each pipeline step light up as it runs', 'The new rule is saved and immediately queryable'],
  },
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
            <span className="nav-ico" aria-hidden>{t.icon}</span>
            <span className="nav-label">{t.label}</span>
          </button>
        ))}
      </nav>

      {/* Per-screen orientation: what this view is + how to use it. Ask has its own hero. */}
      {tab !== 'ask' && (
        <section className="guide" key={active.id}>
          <div className="guide-head">
            <span className="guide-ico" aria-hidden>{active.icon}</span>
            <div>
              <h2 className="guide-title">{active.title}</h2>
              <p className="guide-blurb">{active.blurb}</p>
            </div>
          </div>
          {active.steps && (
            <ol className="guide-steps">
              {active.steps.map((s, i) => (
                <li key={i}><span className="gs-num">{i + 1}</span><span>{s}</span></li>
              ))}
            </ol>
          )}
        </section>
      )}

      <main>
        {tab === 'ask' && <Ask />}
        {tab === 'explorer' && <AsOfExplorer />}
        {tab === 'changes' && <ChangeFeed />}
        {tab === 'timeline' && <ClauseTimeline />}
        {tab === 'comparison' && <Comparison />}
        {tab === 'ingest' && <Ingest />}
      </main>

      <footer className="foot">
        <span className="foot-brand"><span className="foot-dot" aria-hidden />Vidhi — regulatory answers that know <b>who</b> is asking and <b>when</b>.</span>
        <a href="https://github.com/shreyasNaik0101/Vidhi" target="_blank" rel="noreferrer">View the code &#8599;</a>
      </footer>
    </div>
  );
}
