// FastAPI backend client
import { supabase } from './supabase.js';

const API_BASE = 'http://127.0.0.1:8000';

// The backend verifies the Supabase session on every request.
async function headers() {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

export class ApiError extends Error {
  constructor(message, code = 'error') { super(message); this.code = code; }
}

async function errorFrom(res) {
  let msg = `The server returned an error (${res.status}).`;
  let code = `http_${res.status}`;
  try {
    const body = await res.json();
    const d = body.detail;
    if (d && typeof d === 'object' && !Array.isArray(d)) { msg = d.message || msg; code = d.code || code; }
    else if (Array.isArray(d) && d[0]?.msg) { msg = d[0].msg.replace(/^Value error, /, ''); code = 'invalid_request'; }
  } catch { /* non-JSON error body */ }
  return new ApiError(msg, code);
}

// Non-streaming endpoint (kept for compatibility).
export async function askAI(query) {
  const res = await fetch(`${API_BASE}/ask`, {
    method: 'POST', headers: await headers(), body: JSON.stringify({ query }),
  });
  if (!res.ok) throw await errorFrom(res);
  return res.json();
}

/**
 * Stream an answer over SSE. Callbacks: onSources(sources, mode), onToken(text).
 * Resolves with the final {answer, citations, sources}; rejects with ApiError,
 * or with an AbortError when `signal` is aborted (stop button).
 */
export async function streamAsk(query, { signal, onSources, onToken } = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE}/ask/stream`, {
      method: 'POST', headers: await headers(), body: JSON.stringify({ query }), signal,
    });
  } catch (e) {
    if (e.name === 'AbortError') throw e;
    throw new ApiError('Could not reach the LawTalk server. Check that the backend is running.', 'network');
  }
  if (!res.ok) throw await errorFrom(res);
  if (!res.body) throw new ApiError('The server response could not be read.', 'malformed');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let final = null;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      let event = 'message', data = '';
      for (const line of raw.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim();
        else if (line.startsWith('data:')) data += line.slice(5).trim();
      }
      let payload;
      try { payload = JSON.parse(data); } catch { throw new ApiError('Received a malformed response from the server.', 'malformed'); }
      // mode: "RAG" (legal, with sources) or "LLM" (normal mode, no sources).
      if (event === 'sources') onSources?.(payload.sources || [], payload.mode || 'RAG');
      else if (event === 'token') onToken?.(payload.text || '');
      else if (event === 'done') final = payload;
      else if (event === 'error') throw new ApiError(payload.message || 'Something went wrong.', payload.code);
    }
  }
  if (!final) throw new ApiError('The answer was interrupted before it finished.', 'interrupted');
  return final;
}
