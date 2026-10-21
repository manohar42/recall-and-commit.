import { Fragment, useState } from 'react';
import { Eye, Search } from 'lucide-react';
import { api } from '../api';
import { AIError, Empty, SourceBadge, Spinner } from '../components';
import { fmt } from '../util';

const EXAMPLES = ['Which laptop did Maya choose and why?', 'What did we decide about the lease?', 'What did I promise Mom about the holidays?', 'When is Sam moving and what did I agree to?', 'What was decided at the 4.2 go/no-go meeting?'];

function Paragraph({ text, onCite }) {
  const parts = text.split(/(\[\d+\])/g);
  return <p className="answer">{parts.map((p, i) => {
    const m = p.match(/^\[(\d+)\]$/);
    return m ? <button key={i} className="cite" onClick={() => onCite(Number(m[1]))}>{m[1]}</button> : <Fragment key={i}>{p}</Fragment>;
  })}</p>;
}

export default function Recall({ setError, openConversation }) {
  const [q, setQ] = useState(''), [res, setRes] = useState(null), [busy, setBusy] = useState(false);

  async function ask(question) {
    const text = (question ?? q).trim();
    if (!text) return;
    setQ(text); setBusy(true); setRes(null);
    try { setRes(await api.recall(text)); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  const cite = (n) => {
    const el = document.getElementById(`evidence-${n}`);
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el?.classList.add('flash'); setTimeout(() => el?.classList.remove('flash'), 1200);
  };

  return <section className="panel wide">
    <form className="ask" onSubmit={(e) => { e.preventDefault(); ask(); }}>
      <label htmlFor="q">Ask about anything you discussed</label>
      <div><input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. What did we decide about the lease?" maxLength={500} />
        <button className="primary" disabled={busy || !q.trim()}><Search /> Ask</button></div>
    </form>
    <div className="chips">{EXAMPLES.map((e) => <button key={e} onClick={() => ask(e)}>{e}</button>)}</div>
    {busy && <Spinner label="Searching conversations and writing the answer" />}
    {res && <>
      <AIError error={res.ai_error} />
      <article className={`answer-card ${res.insufficient_evidence ? 'none' : ''}`}>
        <div className="line"><h2>Answer</h2><SourceBadge source={res.answer_source} /></div>
        <Paragraph text={res.answer} onCite={cite} />
      </article>
      {res.results.length > 0 && <><h3 className="section-label">Evidence ({res.results.length})</h3>
        <div className="evidence-list">{res.results.map((r) => <article key={r.index} id={`evidence-${r.index}`} className={res.citations.includes(r.index) ? 'cited' : ''}>
          <div className="line"><strong><span className="cite static">{r.index}</span> {r.conversation_title}</strong><small>{fmt(r.started_at)} · lines {r.sequence_start}-{r.sequence_end}</small></div>
          <pre className="excerpt">{r.excerpt}</pre>
          <button onClick={() => openConversation(r.conversation_id, r.sequence_start, r.sequence_end)}><Eye size={15} /> View conversation</button>
        </article>)}</div></>}
    </>}
    {!res && !busy && <Empty icon={Search} title="Answers come with receipts">You get a short paragraph answer with numbered citations. Click a number or "View conversation" to read the original transcript.</Empty>}
  </section>;
}
