import { useRef, useState } from 'react';
import { Check, Download, Eye, Inbox as InboxIcon, Pencil, Sparkles, Upload, X } from 'lucide-react';
import { api } from '../api';
import { AIBanner, Badge, Empty, SourceBadge, Spinner } from '../components';
import { fmt, fmtRange, fromInput, toInput } from '../util';

function CandidateCard({ c, onDone, openConversation, setError }) {
  const [edit, setEdit] = useState(false), [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ action_text: c.action_text, counterparty: c.counterparty || '', due_text: c.due_text || '',
    due_at: toInput(c.due_at), starts_at: toInput(c.starts_at), ends_at: toInput(c.ends_at) });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function run(fn, msg) {
    setBusy(true);
    try { await fn(); onDone(msg); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  const approve = () => run(() => api.approve(c.id, edit ? {
    action_text: form.action_text.trim(), counterparty: form.counterparty.trim() || null, due_text: form.due_text.trim() || null,
    due_at: fromInput(form.due_at), starts_at: fromInput(form.starts_at), ends_at: fromInput(form.ends_at),
  } : {}), 'Commitment approved and added to the ledger');

  return <article className="candidate">
    <div className="candidate-top">
      <div className="badges"><Badge tone={c.ai_label === 'uncertain' ? 'overdue' : ''}>{c.ai_label || 'commitment'}</Badge><SourceBadge source={c.analysis_source} /><small>{Math.round(c.confidence * 100)}% confidence</small></div>
      <small>{c.conversation_title}</small>
    </div>
    <h3>{c.action_text}</h3>
    <p className="meta">{c.counterparty && <>For {c.counterparty} · </>}{c.starts_at ? fmtRange(c.starts_at, c.ends_at) : c.due_at ? `Due ${fmt(c.due_at)}` : c.due_text ? `"${c.due_text}" (no exact date)` : 'No due date'}</p>
    <blockquote>{c.speaker}: "{c.source_text}"</blockquote>
    {c.ai_explanation && <p className="ai-why"><Sparkles size={14} /> {c.ai_explanation}</p>}
    {edit && <div className="form-grid edit">
      <label className="field full"><span>Action</span><input value={form.action_text} onChange={set('action_text')} /></label>
      <label className="field"><span>Counterparty</span><input value={form.counterparty} onChange={set('counterparty')} /></label>
      <label className="field"><span>Due phrase</span><input value={form.due_text} onChange={set('due_text')} /></label>
      <label className="field"><span>Due at (Phoenix time)</span><input type="datetime-local" value={form.due_at} onChange={set('due_at')} /></label>
      <span />
      <label className="field"><span>Starts at</span><input type="datetime-local" value={form.starts_at} onChange={set('starts_at')} /></label>
      <label className="field"><span>Ends at</span><input type="datetime-local" value={form.ends_at} onChange={set('ends_at')} /></label>
    </div>}
    <div className="actions">
      <button className="primary" disabled={busy || (edit && !form.action_text.trim())} onClick={approve}><Check /> {edit ? 'Save and approve' : 'Approve'}</button>
      <button disabled={busy} onClick={() => setEdit(!edit)}><Pencil /> {edit ? 'Cancel edit' : 'Edit'}</button>
      <button disabled={busy} onClick={() => run(() => api.reject(c.id), 'Candidate rejected')}><X /> Reject</button>
      <button onClick={() => openConversation(c.conversation_id, c.utterance_sequence)}><Eye /> View conversation</button>
    </div>
  </article>;
}

export default function Inbox({ data, ai, refresh, notice, setError, openConversation }) {
  const [progress, setProgress] = useState(null), [busy, setBusy] = useState('');
  const fileRef = useRef(null);
  const status = data.analysis;

  async function importSample() {
    setBusy('import');
    try {
      const r = await api.importSample();
      notice(`Imported ${r.conversations_created} new, ${r.conversations_updated} updated, ${r.conversations_skipped} unchanged conversations`);
      await refresh();
    } catch (e) { setError(e.message); } finally { setBusy(''); }
  }

  async function upload(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setBusy('import');
    try {
      const payload = JSON.parse(await file.text());
      const r = await api.importJson(payload);
      notice(`${file.name}: ${r.conversations_received} conversations read, ${r.conversations_created} created, ${r.conversations_updated} updated`);
      await refresh();
    } catch (err) { setError(err instanceof SyntaxError ? `${file.name} is not valid JSON: ${err.message}` : err.message); } finally { setBusy(''); }
  }

  async function analyzeAll() {
    setBusy('analyze');
    let created = 0, analyzed = 0, failed = 0, errors = [];
    try {
      for (let i = 0; i < 100; i++) {
        const r = await api.analyzeBatch(ai?.configured ? 5 : 25);
        created += r.candidates_created; analyzed += r.analyzed; failed += r.failed; errors = r.errors;
        setProgress({ done: r.total_conversations - r.remaining, total: r.total_conversations, created, source: r.source });
        if (r.remaining === 0 || r.analyzed === 0) break;
        await refresh(true);
      }
      if (errors.length) setError(`AI review stopped early: ${errors[0]}`);
      notice(`Reviewed ${analyzed} conversations${failed ? ` (${failed} failed)` : ''}. ${created} new candidates in the inbox.`);
    } catch (e) { setError(e.message); } finally { setBusy(''); setProgress(null); await refresh(); }
  }

  return <>
    <AIBanner status={ai} />
    <section className="panel">
      <div className="title-row">
        <div><h2>Conversations to review</h2>
          <p>Each conversation is read by {ai?.configured ? `Gemini (${ai.model})` : 'the rules fallback'} before anything reaches this inbox. Only lines spoken by you that are real commitments become candidates. Nothing enters your ledger until you approve it.</p></div>
      </div>
      <div className="toolbar">
        <button className="primary" disabled={!!busy || !status?.remaining} onClick={analyzeAll}><Sparkles /> {ai?.configured ? 'Analyze with Gemini' : 'Analyze (rules fallback)'}{status?.remaining ? ` · ${status.remaining} waiting` : ''}</button>
        <button disabled={!!busy} onClick={importSample}><Download /> Import sample month</button>
        <button disabled={!!busy} onClick={() => fileRef.current?.click()}><Upload /> Upload JSON</button>
        <input ref={fileRef} type="file" accept=".json,application/json" hidden onChange={upload} />
        {status && <small className="muted">{status.analyzed} of {status.total_conversations} conversations analyzed{status.failed ? `, ${status.failed} failed (will retry)` : ''}</small>}
      </div>
      {busy === 'import' && <Spinner label="Importing" />}
      {progress && <div className="progress"><div style={{ width: `${progress.total ? (100 * progress.done) / progress.total : 0}%` }} /><span>{progress.done} / {progress.total} reviewed · {progress.created} new candidates</span></div>}
      {busy === 'analyze' && !progress && <Spinner label="AI is reading conversations" />}
    </section>
    <section className="panel">
      <div className="title-row"><h2>Candidates</h2><Badge>{data.candidates.length}</Badge></div>
      {data.candidates.length === 0 ? <Empty icon={InboxIcon} title="Inbox is clear">{status?.total_conversations ? (status.remaining ? 'Click Analyze to let the AI review your conversations.' : 'All conversations are reviewed. New conversations will show up here after analysis.') : 'Import the sample month or upload your own JSON to get started.'}</Empty> :
        <div className="stack">{data.candidates.map((c) => <CandidateCard key={c.id} c={c} openConversation={openConversation} setError={setError} onDone={(m) => { notice(m); refresh(); }} />)}</div>}
    </section>
  </>;
}
