export const TZ = 'America/Phoenix';
const OFFSET = '-07:00'; // Phoenix does not observe daylight saving time

export function fmt(iso, opts = {}) {
  if (!iso) return '';
  return new Date(iso).toLocaleString('en-US', { timeZone: TZ, weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', ...opts });
}
export const fmtTime = (iso) => (iso ? new Date(iso).toLocaleTimeString('en-US', { timeZone: TZ, hour: 'numeric', minute: '2-digit' }) : '');
export function fmtRange(start, end) {
  if (!start) return '';
  return `${fmt(start)} - ${fmtTime(end)}`;
}
// <input type="datetime-local"> value <-> ISO string, interpreted in America/Phoenix.
export function toInput(iso) {
  if (!iso) return '';
  const d = new Date(new Date(iso).getTime() - 7 * 3600 * 1000);
  return d.toISOString().slice(0, 16);
}
export const fromInput = (value) => (value ? `${value}:00${OFFSET}` : null);
export const sourceLabel = (s) => ({ gemini: 'Gemini', rules: 'Rules fallback', seed: 'Sample ledger', manual: 'Manual' }[s] || s || 'Unknown');
