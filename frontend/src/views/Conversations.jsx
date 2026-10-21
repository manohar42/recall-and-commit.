import { useMemo, useState } from 'react';
import { Eye, MessagesSquare, Sparkles } from 'lucide-react';
import { api } from '../api';
import { Badge, Empty, SourceBadge } from '../components';
import { fmt } from '../util';

export default function Conversations({ list, refresh, notice, setError, openConversation }) {
  const [q, setQ] = useState(''), [busy, setBusy] = useState(null);
  const rows = useMemo(() => {
    const t = q.toLowerCase().trim();
    return t ? list.filter((c) => `${c.title} ${c.participants.join(' ')}`.toLowerCase().includes(t)) : list;
  }, [q, list]);

  async function analyze(c) {
    setBusy(c.id);
    try {
      const r = await api.analyzeConversation(c.id);
      if (r.status === 'failed') setError(r.error || 'Analysis failed');
      else notice(`${c.title}: ${r.candidates_created} candidate(s) sent to the Review inbox`);
      await refresh();
    } catch (e) { setError(e.message); } finally { setBusy(null); }
  }

  return <section className="panel">
    <div className="title-row"><div><h2>All conversations</h2><p>Newest first. Open any conversation to read the full transcript.</p></div><Badge>{list.length}</Badge></div>
    <input className="search" placeholder="Filter by title or person" value={q} onChange={(e) => setQ(e.target.value)} />
    {rows.length === 0 ? <Empty icon={MessagesSquare} title="No conversations">Import the sample month from the Review inbox.</Empty> :
      <div className="table">{rows.map((c) => <article key={c.id} className="row-item">
        <div>
          <strong>{c.title}</strong>
          <small>{fmt(c.started_at)} · {c.participants.join(', ')} · {c.utterance_count} lines</small>
          {c.analysis_summary && <small className="ai-line"><Sparkles size={12} /> {c.analysis_summary}</small>}
        </div>
        <div className="row-actions">
          {c.analysis_status === 'completed' ? <><SourceBadge source={c.analysis_source} /><Badge>{c.candidate_count} candidates</Badge></> :
            c.analysis_status === 'failed' ? <Badge tone="overdue">AI failed</Badge> : <Badge tone="muted">Not analyzed</Badge>}
          <button onClick={() => analyze(c)} disabled={busy === c.id}><Sparkles size={15} /> {busy === c.id ? 'Analyzing' : c.analysis_status === 'completed' ? 'Re-check' : 'Analyze'}</button>
          <button onClick={() => openConversation(c.id)}><Eye size={15} /> View</button>
        </div>
      </article>)}</div>}
  </section>;
}
