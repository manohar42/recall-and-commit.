import { useEffect, useRef, useState } from 'react';
import { Check, Eye, Send, X } from 'lucide-react';
import { api } from '../api';
import { SourceBadge } from '../components';

const STARTERS = ['What did I agree to for Saturday?', 'What did we decide about Thanksgiving?', 'Show my overdue commitments', 'Which laptop did Maya choose?'];

export default function Assistant({ setError, openConversation, refresh, notice }) {
  const [msgs, setMsgs] = useState([{ role: 'bot', text: 'Ask me about your conversations or commitments. I answer from your own transcripts and ledger, and I never change anything without your confirmation.' }]);
  const [text, setText] = useState(''), [session, setSession] = useState(null), [busy, setBusy] = useState(false);
  const end = useRef(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: 'smooth' }), [msgs, busy]);

  async function send(message) {
    const m = (message ?? text).trim();
    if (!m) return;
    setText(''); setMsgs((x) => [...x, { role: 'user', text: m }]); setBusy(true);
    try {
      const r = await api.assistant({ message: m, session_id: session });
      setSession(r.session_id);
      setMsgs((x) => [...x, { role: 'bot', text: r.message, source: r.answer_source, evidence: r.evidence, pending: r.pending_action }]);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function decide(i, change, ok) {
    try {
      if (ok) { await api.confirm(change.id); notice('Change confirmed'); await refresh(); } else { await api.cancel(change.id); }
      setMsgs((x) => x.map((m, j) => (j === i ? { ...m, pending: null, text: `${m.text} (${ok ? 'confirmed' : 'cancelled'})` } : m)));
    } catch (e) { setError(e.message); }
  }

  return <section className="panel assistant">
    <div className="title-row"><div><h2>Voice assistant simulation</h2><p>Simulates how a voice assistant (for example Alexa+) would call this backend. Transcript text is treated as evidence, never as instructions.</p></div></div>
    <div className="chat">
      {msgs.map((m, i) => <article key={i} className={m.role}>
        <p>{m.text}</p>
        {m.source && <SourceBadge source={m.source} />}
        {m.evidence?.length > 0 && <div className="mini-evidence">{m.evidence.slice(0, 3).map((e, k) => <button key={k} className="link" onClick={() => openConversation(e.conversation_id, e.sequence_start || e.sequence, e.sequence_end)}><Eye size={13} /> {e.conversation_title}</button>)}</div>}
        {m.pending && <div className="inline-confirm"><span>Confirm this change?</span><button className="primary" onClick={() => decide(i, m.pending, true)}><Check size={15} /> Confirm</button><button onClick={() => decide(i, m.pending, false)}><X size={15} /> Cancel</button></div>}
      </article>)}
      {busy && <article className="bot typing">Thinking...</article>}
      <div ref={end} />
    </div>
    <div className="chips">{STARTERS.map((s) => <button key={s} onClick={() => send(s)} disabled={busy}>{s}</button>)}</div>
    <form className="composer" onSubmit={(e) => { e.preventDefault(); send(); }}>
      <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Type what you would say" maxLength={1000} />
      <button className="primary" aria-label="Send" disabled={busy || !text.trim()}><Send /></button>
    </form>
  </section>;
}
