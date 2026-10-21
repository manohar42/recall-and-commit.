import { StrictMode, useCallback, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { CalendarClock, FlaskConical, Inbox, LayoutDashboard, ListChecks, Menu, MessageCircle, MessagesSquare, Moon, RefreshCw, Search, ShieldCheck, Sun, X } from 'lucide-react';
import { api } from './api';
import { ConversationModal } from './components';
import Today from './views/Today';
import InboxView from './views/Inbox';
import Conversations from './views/Conversations';
import Ledger from './views/Ledger';
import Recall from './views/Recall';
import WhatIf from './views/WhatIf';
import Assistant from './views/Assistant';
import './styles.css';

const VIEWS = {
  today: ['Today', LayoutDashboard, 'Your commitments at a glance'],
  inbox: ['Review inbox', Inbox, 'AI-reviewed commitments waiting for your approval'],
  conversations: ['Conversations', MessagesSquare, 'Every imported conversation and its AI review'],
  ledger: ['Commitments', ListChecks, 'Approved commitments with evidence'],
  recall: ['Recall', Search, 'Ask questions, get a paragraph answer with citations'],
  whatif: ['What If', FlaskConical, 'Explore a change before it touches your ledger'],
  assistant: ['Assistant', MessageCircle, 'Voice assistant simulation'],
};
const EMPTY = { candidates: [], commitments: [], review: null, conversations: [], conversationCount: 0, analysis: null };

function App() {
  const [view, setView] = useState(() => location.hash.slice(1) in VIEWS ? location.hash.slice(1) : 'today');
  const [dark, setDark] = useState(() => matchMedia('(prefers-color-scheme: dark)').matches);
  const [menu, setMenu] = useState(false), [data, setData] = useState(EMPTY), [ai, setAi] = useState(null);
  const [loading, setLoading] = useState(true), [error, setError] = useState(''), [toast, setToast] = useState(''), [modal, setModal] = useState(null);

  useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light'; }, [dark]);
  useEffect(() => { location.hash = view; }, [view]);

  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true);
    try {
      const [candidates, commitments, review, conversations, analysis, status] = await Promise.all([
        api.candidates(), api.commitments(), api.review(), api.conversations(), api.analysisStatus(), api.aiStatus()]);
      setData({ candidates, commitments, review, conversations, conversationCount: conversations.length, analysis });
      setAi(status);
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const notice = (msg) => { setToast(msg); setTimeout(() => setToast(''), 3500); };
  const openConversation = (id, from, to) => setModal({ id, from, to });
  const common = { refresh, notice, setError, openConversation };
  const [title, , subtitle] = VIEWS[view];

  return <div className="app">
    <aside className={menu ? 'open' : ''}>
      <div className="brand"><svg viewBox="0 0 40 40" aria-hidden="true"><path d="M8 20a12 12 0 1 1 4 9" /><path d="M8 29v-9h9" /><path d="m17 20 3 3 7-8" /></svg><div><strong>Recall & Commit</strong><small>Evidence-backed memory</small></div></div>
      <nav>{Object.entries(VIEWS).map(([k, [label, Icon]]) => <button key={k} className={view === k ? 'active' : ''} onClick={() => { setView(k); setMenu(false); }}>
        <Icon /><span>{label}</span>{k === 'inbox' && data.candidates.length > 0 && <b>{data.candidates.length}</b>}</button>)}</nav>
      <div className="side-note"><span className={`dot ${ai?.configured ? '' : 'off'}`} /><div><strong>{ai ? (ai.configured ? 'Gemini active' : 'Rules fallback') : 'Connecting...'}</strong><small>{ai ? `${ai.framework} · ${ai.model}` : ''}</small></div></div>
    </aside>
    {menu && <div className="scrim" onClick={() => setMenu(false)} />}
    <div className="shell">
      <header>
        <div className="header-title"><button className="icon mobile" onClick={() => setMenu(true)} aria-label="Menu"><Menu /></button>
          <div><p className="eyebrow">{subtitle}</p><h1>{title}</h1></div></div>
        <div className="header-actions"><span className="trust"><ShieldCheck /> Nothing changes without your approval</span>
          <button className="icon" onClick={() => refresh()} aria-label="Refresh"><RefreshCw className={loading ? 'spin' : ''} /></button>
          <button className="icon" onClick={() => setDark(!dark)} aria-label="Toggle theme">{dark ? <Sun /> : <Moon />}</button></div>
      </header>
      <main id="main">
        {error && <div className="alert" role="alert"><span>{error}</span><button onClick={() => setError('')} aria-label="Dismiss"><X /></button></div>}
        {loading && !data.review ? <div className="skeleton-wrap"><div /><div /><div /><section /></div> : <>
          {view === 'today' && <Today data={data} ai={ai} go={setView} openConversation={openConversation} />}
          {view === 'inbox' && <InboxView data={data} ai={ai} {...common} />}
          {view === 'conversations' && <Conversations list={data.conversations} {...common} />}
          {view === 'ledger' && <Ledger commitments={data.commitments} {...common} />}
          {view === 'recall' && <Recall {...common} />}
          {view === 'whatif' && <WhatIf commitments={data.commitments} {...common} />}
          {view === 'assistant' && <Assistant {...common} />}
        </>}
      </main>
    </div>
    {modal && <ConversationModal {...modal} onClose={() => setModal(null)} />}
    {toast && <div className="toast" role="status"><CalendarClock /> {toast}</div>}
  </div>;
}

createRoot(document.getElementById('root')).render(<StrictMode><App /></StrictMode>);
