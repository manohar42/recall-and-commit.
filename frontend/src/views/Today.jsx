import { CalendarClock, Inbox } from 'lucide-react';
import { AIBanner, Badge, Empty } from '../components';
import { fmt, fmtRange } from '../util';

function Group({ title, items, tone, openConversation }) {
  return <section className="panel">
    <div className="title-row"><h2>{title}</h2><Badge tone={tone}>{items.length}</Badge></div>
    {items.length === 0 ? <p className="muted">Nothing here.</p> : <div className="stack">
      {items.slice(0, 6).map((c) => <article key={c.id} className="row-item">
        <div><strong>{c.action_text}</strong><small>{c.starts_at ? fmtRange(c.starts_at, c.ends_at) : c.due_at ? `Due ${fmt(c.due_at)}` : 'No date'}{c.counterparty ? ` · ${c.counterparty}` : ''}</small></div>
        {c.source && <button className="link" onClick={() => openConversation(c.source.conversation_id, c.source.sequence)}>Evidence</button>}
      </article>)}
    </div>}
  </section>;
}

export default function Today({ data, ai, go, openConversation }) {
  const r = data.review || { overdue: [], due_soon: [], undated: [], recently_completed: [] };
  const open = data.commitments.filter((c) => c.status === 'open').length;
  const nothing = data.conversationCount === 0;
  return <>
    <AIBanner status={ai} />
    <div className="metrics">
      <button className="metric" onClick={() => go('inbox')}><p>Waiting for review</p><strong>{data.candidates.length}</strong><span>AI-reviewed candidates</span></button>
      <button className="metric" onClick={() => go('ledger')}><p>Open commitments</p><strong>{open}</strong><span>in your ledger</span></button>
      <button className="metric" onClick={() => go('ledger')}><p>Overdue</p><strong className={r.overdue.length ? 'warn' : ''}>{r.overdue.length}</strong><span>past due date</span></button>
      <button className="metric" onClick={() => go('conversations')}><p>Conversations</p><strong>{data.conversationCount}</strong><span>{data.analysis ? `${data.analysis.analyzed} reviewed by ${ai?.configured ? 'Gemini' : 'rules'}` : ''}</span></button>
    </div>
    {nothing ? <section className="panel"><Empty icon={Inbox} title="No conversations yet">Go to the Review inbox and click "Import sample month", or run the seed command from the README.</Empty>
      <div className="center"><button className="primary" onClick={() => go('inbox')}>Open Review inbox</button></div></section> :
      <div className="grid2">
        <Group title="Overdue" tone="overdue" items={r.overdue} openConversation={openConversation} />
        <Group title="Due in the next 7 days" items={r.due_soon} openConversation={openConversation} />
        <Group title="No date yet" items={r.undated} openConversation={openConversation} />
        <Group title="Recently completed" tone="done" items={r.recently_completed} openConversation={openConversation} />
      </div>}
    {!nothing && data.commitments.length === 0 && <Empty icon={CalendarClock} title="Ledger is empty">Approve candidates in the Review inbox to build your commitment ledger.</Empty>}
  </>;
}
