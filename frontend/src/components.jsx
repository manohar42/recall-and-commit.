import { useEffect, useState } from 'react';
import { AlertTriangle, Bot, Loader2, Sparkles, X } from 'lucide-react';
import { api } from './api';
import { fmt, sourceLabel } from './util';

export function Badge({ children, tone = '' }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function SourceBadge({ source }) {
  if (!source) return null;
  return <span className={`badge src-${source}`}>{source === 'gemini' ? <Sparkles size={12} /> : <Bot size={12} />} {sourceLabel(source)}</span>;
}

export function Empty({ icon: Icon, title, children }) {
  return <div className="empty">{Icon && <Icon />}<h3>{title}</h3><p>{children}</p></div>;
}

export function Spinner({ label }) {
  return <span className="spinner"><Loader2 size={16} className="spin" /> {label}</span>;
}

export function AIBanner({ status, compact = false }) {
  if (!status) return null;
  if (status.configured) {
    return <div className="ai-banner ok"><Sparkles size={18} /><div><strong>Gemini active</strong>{!compact && <p>{status.model} via {status.framework}. Commitments, Recall and What If use the model.</p>}</div></div>;
  }
  return <div className="ai-banner warn"><AlertTriangle size={18} /><div><strong>Gemini not configured - using rules fallback</strong>{!compact && <p>Add <code>GOOGLE_API_KEY</code> to the <code>.env</code> file in the project folder, then run <code>docker compose up -d --force-recreate api</code>.</p>}</div></div>;
}

export function AIError({ error }) {
  if (!error) return null;
  return <div className="alert soft"><AlertTriangle size={16} /> <span>Gemini was unavailable, so this used the rules fallback: {error}</span></div>;
}

export function Modal({ title, subtitle, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return <div className="modal-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
    <section className="modal" role="dialog" aria-modal="true" aria-label={title}>
      <div className="modal-head"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button className="icon" onClick={onClose} aria-label="Close"><X /></button></div>
      <div className="modal-body">{children}</div>
    </section>
  </div>;
}

/** Full transcript; lines in [from, to] are highlighted and scrolled into view. */
export function ConversationModal({ id, from, to, onClose }) {
  const [conv, setConv] = useState(null), [error, setError] = useState('');
  useEffect(() => { api.conversation(id).then(setConv).catch((e) => setError(e.message)); }, [id]);
  useEffect(() => {
    if (conv && from) document.getElementById(`line-${from}`)?.scrollIntoView({ block: 'center' });
  }, [conv, from]);
  return <Modal title={conv?.title || 'Conversation'} subtitle={conv ? `${fmt(conv.started_at)} · ${conv.participants.join(', ')} · you are ${conv.user_speaker || 'not set'}` : ''} onClose={onClose}>
    {error && <p className="error">{error}</p>}
    {!conv && !error && <Spinner label="Loading conversation" />}
    {conv?.analysis_summary && <p className="ai-summary"><Sparkles size={14} /> {conv.analysis_summary}</p>}
    <ol className="transcript">
      {conv?.utterances.map((u) => {
        const hit = from && u.sequence >= from && u.sequence <= (to || from);
        return <li key={u.id} id={`line-${u.sequence}`} className={`${hit ? 'hit' : ''} ${u.speaker === conv.user_speaker ? 'me' : ''}`}>
          <span className="who">{u.speaker}</span><span className="when">{fmt(u.occurred_at, { weekday: undefined, month: undefined, day: undefined })}</span>
          <p>{u.text}</p>
        </li>;
      })}
    </ol>
  </Modal>;
}
