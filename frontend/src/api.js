// Relative by default so the same build works behind Vite (dev) and nginx (Docker).
const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

export async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(API + path, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
  } catch {
    throw new Error('Cannot reach the API. Is the backend running (docker compose ps)?');
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : data.error?.message;
    throw new Error(detail || `Request failed (${response.status} ${response.statusText})`);
  }
  return data;
}

const post = (path, body) => request(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
const patch = (path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body) });

export const api = {
  health: () => request('/api/health'),
  aiStatus: () => request('/api/ai/status'),
  analysisStatus: () => request('/api/ai/commitments/status'),
  analyzeBatch: (limit = 10) => post(`/api/ai/commitments/analyze?limit=${limit}`),
  sampleInfo: () => request('/api/imports/sample/info'),
  importSample: () => post('/api/imports/sample'),
  importJson: (payload) => post('/api/imports/json', payload),
  conversations: () => request('/api/conversations'),
  conversation: (id) => request(`/api/conversations/${id}`),
  analyzeConversation: (id) => post(`/api/conversations/${id}/analyze`),
  candidates: (status = 'pending') => request(`/api/commitments/candidates?status=${status}`),
  approve: (id, body = {}) => post(`/api/commitments/candidates/${id}/approve`, body),
  reject: (id) => post(`/api/commitments/candidates/${id}/reject`),
  review: () => request('/api/commitments/review'),
  commitments: (status) => request(`/api/commitments${status ? `?status=${status}` : ''}`),
  patchCommitment: (id, body) => patch(`/api/commitments/${id}`, body),
  history: (id) => request(`/api/commitments/${id}/history`),
  recall: (question) => post('/api/recall', { question, limit: 6 }),
  createScenario: (body) => post('/api/scenarios', body),
  evaluate: (id) => post(`/api/scenarios/${id}/evaluate`),
  prepare: (id) => post(`/api/scenarios/${id}/prepare-change`),
  confirm: (id) => post(`/api/commitment-changes/${id}/confirm`),
  cancel: (id) => post(`/api/commitment-changes/${id}/cancel`),
  assistant: (body) => post('/api/assistant/messages', body),
};
