import { useState } from 'react';
import { Check, Eye, ListChecks, Undo2 } from 'lucide-react';
import { api } from '../api';
import { Badge, Empty } from '../components';
import { fmt, fmtRange } from '../util';

const FILTERS = { open: 'Open', done: 'Done', cancelled: 'Cancelled', all: 'All' };

export default function Ledger({ commitments, refresh, notice, setError, openConversation }) {
  const [filter, setFilter] = useState('open');
  const rows = commitments.filter((c) => filter === 'all' || c.status === filter)
    .sort((a, b) => (a.starts_at || a.due_at || '9999').localeCompare(b.starts_at || b.due_at || '9999'));

  async function setStatus(c, status) {
    try { await api.patchCommitment(c.id, { status }); notice(status === 'done' ? 'Marked done' : 'Reopened'); await refresh(); }
    catch (e) { setError(e.message); }
  }

  return <section className="panel">
    <div className="title-row"><div><h2>Commitment ledger</h2><p>Only commitments you approved. Every item links back to the exact line that created it.</p></div></div>
    <div className="filters">{Object.entries(FILTERS).map(([k, v]) => <button key={k} className={filter === k ? 'selected' : ''} onClick={() => setFilter(k)}>{v} ({k === 'all' ? commitments.length : commitments.filter((c) => c.status === k).length})</button>)}</div>
    {rows.length === 0 ? <Empty icon={ListChecks} title="Nothing here">Approve candidates in the Review inbox to add commitments.</Empty> :
      <div className="stack">{rows.map((c) => <article key={c.id} className="commitment">
        <button className="check" aria-label={c.status === 'done' ? 'Reopen' : 'Mark done'} onClick={() => setStatus(c, c.status === 'done' ? 'open' : 'done')}>{c.status === 'done' ? <Undo2 /> : <Check />}</button>
        <div>
          <div className="line"><h3 className={c.status === 'done' ? 'struck' : ''}>{c.action_text}</h3><Badge tone={c.due_group === 'overdue' && c.status === 'open' ? 'overdue' : c.status === 'done' ? 'done' : ''}>{c.status === 'open' ? c.due_group : c.status}</Badge></div>
          <p>{c.counterparty ? `For ${c.counterparty} · ` : ''}{c.starts_at ? fmtRange(c.starts_at, c.ends_at) : c.due_at ? `Due ${fmt(c.due_at)}` : 'No date'}{c.due_text ? ` · said "${c.due_text}"` : ''}</p>
          {c.source && <div className="evidence-row"><blockquote>{c.source.speaker}: "{c.source.text}"</blockquote>
            <button className="link" onClick={() => openConversation(c.source.conversation_id, c.source.sequence)}><Eye size={14} /> {c.source.conversation_title}</button></div>}
        </div>
      </article>)}</div>}
  </section>;
}
