import { useMemo, useState } from 'react';
import { CalendarClock, Check, FlaskConical, ShieldCheck, X } from 'lucide-react';
import { api } from '../api';
import { AIError, Badge, Empty, SourceBadge, Spinner } from '../components';
import { fmt, fmtRange, fromInput, toInput } from '../util';

const RISK = { clear: ['No conflicts', 'done'], caution: ['Needs attention', ''], conflict: ['Conflict found', 'overdue'] };
const DEFAULT = { action_text: "Help Maya decorate Lucia's before her birthday dinner", counterparty: 'Maya', starts_at: '2026-10-24T16:45', ends_at: '2026-10-24T18:15' };

export default function WhatIf({ commitments, refresh, notice, setError }) {
  const open = useMemo(() => commitments.filter((c) => c.status === 'open'), [commitments]);
  const [op, setOp] = useState('add'), [target, setTarget] = useState(''), [form, setForm] = useState(DEFAULT);
  const [scenario, setScenario] = useState(null), [prepared, setPrepared] = useState(null), [busy, setBusy] = useState('');
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  function pickTarget(id) {
    setTarget(id);
    const c = open.find((x) => String(x.id) === String(id));
    if (c) setForm({ action_text: c.action_text, counterparty: c.counterparty || '', starts_at: toInput(c.starts_at || c.due_at), ends_at: toInput(c.ends_at || c.due_at) });
  }

  async function evaluate(e) {
    e.preventDefault();
    if ((form.starts_at && !form.ends_at) || (!form.starts_at && form.ends_at)) return setError('Enter both a start and an end time.');
    setBusy('eval'); setScenario(null); setPrepared(null);
    try {
      const change = { action_text: form.action_text.trim() || null, counterparty: form.counterparty.trim() || null,
        starts_at: fromInput(form.starts_at), ends_at: fromInput(form.ends_at), timezone_name: 'America/Phoenix' };
      const s = await api.createScenario({ operation: op, target_commitment_id: op === 'update' ? Number(target) : null, proposed_change: change });
      setScenario(await api.evaluate(s.id));
    } catch (err) { setError(err.message); } finally { setBusy(''); }
  }
  async function prepare() {
    setBusy('prep');
    try { setPrepared(await api.prepare(scenario.id)); } catch (e) { setError(e.message); } finally { setBusy(''); }
  }
  async function confirm() {
    setBusy('confirm');
    try { await api.confirm(prepared.id); notice(op === 'add' ? 'Added to your ledger' : 'Commitment updated'); setScenario(null); setPrepared(null); await refresh(); }
    catch (e) { setError(e.message); } finally { setBusy(''); }
  }
  async function cancel() {
    try { await api.cancel(prepared.id); setPrepared(null); notice('Prepared change cancelled. Nothing was changed.'); } catch (e) { setError(e.message); }
  }

  const risk = scenario && (RISK[scenario.risk_level] || RISK.caution);
  return <div className="what-grid">
    <form className="panel" onSubmit={evaluate}>
      <h2>Try a change safely</h2>
      <p className="muted">Nothing is saved while you explore. The AI explains the impact; you confirm separately.</p>
      <div className="filters">{['add', 'update'].map((o) => <button type="button" key={o} className={op === o ? 'selected' : ''} onClick={() => { setOp(o); setScenario(null); if (o === 'add') setForm(DEFAULT); }}>{o === 'add' ? 'Add a new task' : 'Move an existing one'}</button>)}</div>
      <div className="form-grid">
        {op === 'update' && <label className="field full"><span>Commitment to change</span>
          <select value={target} onChange={(e) => pickTarget(e.target.value)} required><option value="">Choose...</option>
            {open.map((c) => <option key={c.id} value={c.id}>{c.action_text}{c.starts_at || c.due_at ? ` (${fmt(c.starts_at || c.due_at)})` : ''}</option>)}</select></label>}
        <label className="field full"><span>What</span><input value={form.action_text} onChange={set('action_text')} required={op === 'add'} /></label>
        <label className="field full"><span>With / for</span><input value={form.counterparty} onChange={set('counterparty')} /></label>
        <label className="field"><span>Starts (Phoenix time)</span><input type="datetime-local" value={form.starts_at} onChange={set('starts_at')} /></label>
        <label className="field"><span>Ends</span><input type="datetime-local" value={form.ends_at} onChange={set('ends_at')} /></label>
      </div>
      <button className="primary full-btn" disabled={busy === 'eval' || (op === 'update' && !target)}><FlaskConical /> Check this plan</button>
    </form>
    <section className="panel">
      {busy === 'eval' && <Spinner label="Checking the ledger and writing the explanation" />}
      {!scenario && busy !== 'eval' && <Empty icon={CalendarClock} title="See the impact first">The default example overlaps with Saturday, October 24 in the sample data, so you can see a conflict explained.</Empty>}
      {scenario && <>
        <AIError error={scenario.ai_error} />
        <div className="line"><h2>What would happen</h2><div className="badges"><Badge tone={risk[1]}>{risk[0]}</Badge><SourceBadge source={scenario.explanation_source} /></div></div>
        <p className="answer">{scenario.explanation}</p>
        {scenario.findings.length > 0 && <><h3 className="section-label">Checks</h3><div className="findings">{scenario.findings.map((f) => <article key={f.id} className={f.type}><strong>{f.type.replace('_', ' ')}</strong><p>{f.explanation}</p></article>)}</div></>}
        {scenario.related_commitments?.length > 0 && <><h3 className="section-label">Already on that day</h3><ul className="related">{scenario.related_commitments.map((r) => <li key={r.id}><strong>{r.action}</strong> <small>{r.when}</small></li>)}</ul></>}
        {!prepared ? <div className="actions"><button className="primary" onClick={prepare} disabled={busy === 'prep'}><ShieldCheck /> {scenario.risk_level === 'conflict' ? 'Prepare anyway' : 'Prepare change'}</button></div> :
          <div className="confirm-box"><div><strong>Ready to confirm</strong><small>{prepared.exact_payload.action_text || form.action_text} · {fmtRange(prepared.exact_payload.starts_at, prepared.exact_payload.ends_at) || 'no time'} · expires {fmt(prepared.expires_at)}</small></div>
            <div className="actions"><button className="primary" onClick={confirm} disabled={busy === 'confirm'}><Check /> Confirm</button><button onClick={cancel}><X /> Cancel</button></div></div>}
      </>}
    </section>
  </div>;
}
