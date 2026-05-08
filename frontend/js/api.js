// FastAPI backend client
const API_URL = 'http://127.0.0.1:8000/ask';

export async function askAI(query) {
  const res = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query })
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  const data = await res.json();
  // Backend returns { answer, mode } — fall back to other common keys just in case
  return data.answer ?? data.response ?? data.message ?? '';
}
