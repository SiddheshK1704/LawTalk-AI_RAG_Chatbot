// LawTalk workspace: conversations (Supabase), streaming answers, evidence panel.
import { supabase } from './supabase.js';
import { requireAuth, logout, onAuthChange } from './auth.js';
import { streamAsk } from './api.js';
import { renderMarkdown, plainAnswer } from './markdown.js';
import { initThemeToggles } from './theme.js';

const $ = (id) => document.getElementById(id);
const app = $('app');
const scrollEl = $('scroll');
const messagesEl = $('messages');
const emptyState = $('emptyState');
const form = $('chatForm');
const input = $('chatInput');
const sendBtn = $('sendBtn');
const stopBtn = $('stopBtn');
const chatListEl = $('chatList');
const chatListEmpty = $('chatListEmpty');
const searchEl = $('chatSearch');
const titleEl = $('chatTitle');
const evidenceBody = $('evidenceBody');
const evidenceCount = $('evidenceCount');
const toggleEvidenceBtn = $('toggleEvidence');
const scrim = $('scrim');
const statusEl = $('status');

const mqDesktop = window.matchMedia('(min-width: 1024px)');
const mqTablet = window.matchMedia('(min-width: 768px)');

let session = null;
let currentChatId = null;
let chats = [];
let busy = false;
let controller = null;
let sourcesColumn = true;       // set false if the messages table has no `sources` column
const thread = [];              // assistant message records in the open conversation

const ICONS = {
  copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
  retry: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>',
  book: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5V5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-1.5zM8 7h6M8 11h6"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  mark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18M5 21h14M7 7h10M4 7l-2 6a3 3 0 0 0 6 0L6 7M18 7l-2 6a3 3 0 0 0 6 0l-2-6"/></svg>',
};

function el(tag, className, text) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text != null) n.textContent = text;
  return n;
}
function iconButton(icon, label, cls = 'icon-btn') {
  const b = el('button', cls);
  b.type = 'button';
  b.setAttribute('aria-label', label);
  b.dataset.tip = label;
  b.innerHTML = ICONS[icon]; // static icon markup, no user data
  return b;
}
function announce(msg) { statusEl.textContent = ''; setTimeout(() => { statusEl.textContent = msg; }, 30); }

let toastTimer;
function toast(msg) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 1800);
}
const storage = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* private mode */ } },
};

/* ================= Init ================= */
initThemeToggles();
(async () => {
  session = await requireAuth();
  if (!session) return;
  const email = session.user.email || '';
  $('userEmail').textContent = email;
  $('userAvatar').textContent = (email[0] || 'U').toUpperCase();
  if (storage.get('lt.sidebar') === 'collapsed' && mqTablet.matches) app.classList.add('sidebar-collapsed');
  await loadChats();
  input.focus();
})();

onAuthChange((s) => { if (!s) window.location.href = 'index.html'; });
$('logoutBtn').addEventListener('click', () => logout());

/* ================= Sidebar & panels ================= */
function setSidebar(open) {
  if (mqTablet.matches) {
    app.classList.toggle('sidebar-collapsed', !open);
    storage.set('lt.sidebar', open ? 'open' : 'collapsed');
  } else {
    app.classList.toggle('sidebar-open-mobile', open);
    if (open) $('closeSidebar').focus();
  }
  syncScrim();
}
function sidebarOpen() {
  return mqTablet.matches ? !app.classList.contains('sidebar-collapsed') : app.classList.contains('sidebar-open-mobile');
}
$('openSidebar').addEventListener('click', () => setSidebar(!sidebarOpen()));
$('collapseSidebar').addEventListener('click', () => setSidebar(false));
$('closeSidebar').addEventListener('click', () => { setSidebar(false); $('openSidebar').focus(); });

function evidenceOpen() {
  return mqDesktop.matches ? !app.classList.contains('evidence-closed') : app.classList.contains('evidence-open-mobile');
}
function setEvidence(open, { focus = false } = {}) {
  if (mqDesktop.matches) app.classList.toggle('evidence-closed', !open);
  else app.classList.toggle('evidence-open-mobile', open);
  toggleEvidenceBtn.setAttribute('aria-expanded', String(open));
  if (open && focus && !mqDesktop.matches) $('closeEvidence').focus();
  syncScrim();
}
toggleEvidenceBtn.addEventListener('click', () => setEvidence(!evidenceOpen(), { focus: true }));
$('closeEvidence').addEventListener('click', () => { setEvidence(false); toggleEvidenceBtn.focus(); });

function syncScrim() {
  const show = (!mqTablet.matches && app.classList.contains('sidebar-open-mobile'))
    || (!mqDesktop.matches && app.classList.contains('evidence-open-mobile'));
  scrim.classList.toggle('show', show);
}
scrim.addEventListener('click', () => {
  app.classList.remove('sidebar-open-mobile', 'evidence-open-mobile');
  toggleEvidenceBtn.setAttribute('aria-expanded', 'false');
  syncScrim();
});
[mqDesktop, mqTablet].forEach((mq) => mq.addEventListener('change', () => {
  app.classList.remove('sidebar-open-mobile', 'evidence-open-mobile');
  syncScrim();
}));

document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  if ($('confirmDialog').classList.contains('show')) return; // handled by dialog
  if (app.classList.contains('evidence-open-mobile')) { setEvidence(false); toggleEvidenceBtn.focus(); }
  else if (app.classList.contains('sidebar-open-mobile')) { setSidebar(false); $('openSidebar').focus(); }
  else if (busy) controller?.abort();
});

/* ================= Conversation list ================= */
async function loadChats() {
  const { data, error } = await supabase
    .from('chats').select('*').eq('user_id', session.user.id).order('created_at', { ascending: false });
  if (error) { toast('Could not load conversations.'); console.error(error); return; }
  chats = data || [];
  renderChatList();
}

function renderChatList() {
  const q = searchEl.value.trim().toLowerCase();
  const shown = chats.filter((c) => !q || (c.title || '').toLowerCase().includes(q));
  chatListEl.replaceChildren();
  chatListEmpty.hidden = shown.length > 0;
  chatListEmpty.textContent = chats.length ? 'No matching conversations.' : 'No conversations yet.';
  for (const c of shown) {
    const li = el('li', 'chat-item' + (c.id === currentChatId ? ' active' : ''));
    const open = el('button', 'chat-open');
    open.type = 'button';
    open.append(el('span', 'chat-title', c.title || 'Untitled'));
    const arrow = el('span', 'nudge');
    arrow.setAttribute('aria-hidden', 'true');
    arrow.innerHTML = ICONS.arrow; // static icon
    open.append(arrow);
    open.title = c.title || '';
    if (c.id === currentChatId) open.setAttribute('aria-current', 'true');
    open.addEventListener('click', () => openChat(c));
    const del = iconButton('trash', 'Delete conversation', 'icon-btn chat-del');
    delete del.dataset.tip;
    del.addEventListener('click', () => confirmDelete(c));
    li.append(open, del);
    chatListEl.append(li);
  }
}
searchEl.addEventListener('input', renderChatList);

/* Delete with a confirm dialog */
function confirmDelete(chat) {
  const dlg = $('confirmDialog');
  const ok = $('confirmOk'), cancel = $('confirmCancel');
  const prev = document.activeElement;
  $('confirmText').textContent = `“${chat.title || 'Untitled'}” and its messages will be permanently deleted.`;
  dlg.classList.add('show');
  dlg.setAttribute('aria-hidden', 'false');
  cancel.focus();
  const close = () => {
    dlg.classList.remove('show');
    dlg.setAttribute('aria-hidden', 'true');
    ok.removeEventListener('click', onOk); cancel.removeEventListener('click', close);
    dlg.removeEventListener('keydown', onKey); dlg.removeEventListener('click', onBackdrop);
    prev?.focus?.();
  };
  const onOk = async () => { close(); await deleteChat(chat); };
  const onKey = (e) => {
    if (e.key === 'Escape') { e.stopPropagation(); close(); }
    if (e.key === 'Tab') { e.preventDefault(); (document.activeElement === ok ? cancel : ok).focus(); }
  };
  const onBackdrop = (e) => { if (e.target === dlg) close(); };
  ok.addEventListener('click', onOk); cancel.addEventListener('click', close);
  dlg.addEventListener('keydown', onKey); dlg.addEventListener('click', onBackdrop);
}

async function deleteChat(chat) {
  // Messages first, in case the FK has no ON DELETE CASCADE.
  const { error: msgErr } = await supabase.from('messages').delete().eq('chat_id', chat.id);
  if (msgErr) { toast('Could not delete messages.'); console.error(msgErr); return; }
  const { error, count } = await supabase.from('chats').delete({ count: 'exact' })
    .eq('id', chat.id).eq('user_id', session.user.id);
  if (error || count === 0) { toast('Could not delete the conversation.'); console.error(error); return; }
  if (currentChatId === chat.id) startNewChat();
  chats = chats.filter((c) => c.id !== chat.id);
  renderChatList();
  toast('Conversation deleted');
}

/* ================= Opening / new ================= */
function resetThread() {
  if (busy) controller?.abort();
  requestSeq++;            // any in-flight callbacks now belong to a stale request
  messagesEl.replaceChildren();
  thread.length = 0;
  clearEvidence();
}

// Evidence belongs to one legal (RAG) answer. Normal-mode answers have none, and the
// panel is closed and emptied so nothing from an earlier request can be shown.
function clearEvidence() {
  showEvidence(null);
  setEvidence(false);
}
let requestSeq = 0;

function startNewChat() {
  resetThread();
  currentChatId = null;
  titleEl.textContent = 'New conversation';
  emptyState.hidden = false;
  emptyState.classList.remove('leaving');
  renderChatList();
  if (!mqTablet.matches) setSidebar(false);
  input.focus();
}
$('newChatBtn').addEventListener('click', startNewChat);

async function openChat(chat) {
  resetThread();
  currentChatId = chat.id;
  titleEl.textContent = chat.title || 'Untitled';
  emptyState.hidden = true;
  renderChatList();
  if (!mqTablet.matches) setSidebar(false);
  const { data, error } = await supabase
    .from('messages').select('*').eq('chat_id', chat.id).order('created_at', { ascending: true });
  if (currentChatId !== chat.id) return; // another chat was opened meanwhile
  if (error) { toast('Could not load messages.'); console.error(error); return; }
  let lastQuestion = '';
  for (const m of data || []) {
    if (m.role === 'user') { addUser(m.content, false); lastQuestion = m.content; }
    else {
      const rec = addAssistant(lastQuestion, false);
      rec.rowId = m.id;
      rec.sources = Array.isArray(m.sources) ? m.sources : [];
      rec.mode = rec.sources.length ? 'RAG' : null;  // mode is not stored; saved sources imply RAG
      finishAssistant(rec, m.content);
    }
  }
  const last = thread[thread.length - 1];
  if (last?.sources.length) {
    showEvidence(last);
    if (mqDesktop.matches) setEvidence(true);
  } else {
    clearEvidence();
  }
  scrollToBottom(true);
}

/* ================= Composer ================= */
function autosize() {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 200) + 'px';
  sendBtn.disabled = busy || !input.value.trim();
}
input.addEventListener('input', autosize);
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
});
form.addEventListener('submit', (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || busy) return;
  if (text.length > 2000) { toast('Questions are limited to 2,000 characters.'); return; }
  input.value = '';
  autosize();
  send(text);
});
stopBtn.addEventListener('click', () => controller?.abort());
document.querySelectorAll('.suggestion').forEach((b) => b.addEventListener('click', () => {
  if (!busy) send(b.dataset.q);
}));

function setBusy(v) {
  busy = v;
  sendBtn.hidden = v;
  stopBtn.hidden = !v;
  autosize();
  if (v) stopBtn.focus({ preventScroll: true }); else if (document.activeElement === stopBtn || document.activeElement === document.body) input.focus();
}

/* ================= Messages ================= */
function nearBottom() { return scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight < 120; }
function scrollToBottom(force = false) {
  if (force || nearBottom()) scrollEl.scrollTop = scrollEl.scrollHeight;
}

function hideEmptyState() {
  if (emptyState.hidden) return;
  emptyState.classList.add('leaving');
  setTimeout(() => { emptyState.hidden = true; emptyState.classList.remove('leaving'); }, 180);
}

const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Message fade-in with GSAP; falls back to the CSS keyframe if GSAP didn't load.
function reveal(row, animate) {
  if (!animate || reduceMotion()) { row.classList.add('no-anim'); return; }
  if (window.gsap) {
    row.classList.add('no-anim');
    window.gsap.from(row, { opacity: 0, y: 6, duration: 0.28, ease: 'power2.out', clearProps: 'all' });
  }
}

function addUser(text, animate = true) {
  const row = el('div', 'msg msg-user');
  row.append(el('span', 't-label msg-role', 'You'), el('div', 'bubble', text));
  messagesEl.append(row);
  reveal(row, animate);
  return row;
}

function addAssistant(question, animate = true) {
  const row = el('div', 'msg msg-ai');
  const avatar = el('span', 'brand-mark avatar');
  avatar.setAttribute('aria-hidden', 'true');
  avatar.innerHTML = ICONS.mark; // static icon
  const col = el('div');
  const role = el('span', 't-label msg-role');
  role.append(document.createTextNode('LAW/TALK'));
  const modeTag = el('span', 'msg-mode');
  role.append(modeTag);
  const body = el('div', 'prose');
  col.append(role, body);
  row.append(avatar, col);
  messagesEl.append(row);
  reveal(row, animate);
  const rec = { row, col, body, modeTag, question, answer: '', sources: [], mode: null, rowId: null };
  thread.push(rec);
  return rec;
}

function showThinking(rec) {
  rec.body.replaceChildren();
  rec.col.querySelector('.msg-actions')?.remove();
  rec.col.querySelector('.msg-note')?.remove();
  const t = el('div', 'thinking');
  const dots = el('span', 'dots');
  dots.append(el('span'), el('span'), el('span'));
  t.append(dots, el('span', null, 'Searching the legal sources…'));
  rec.body.append(t);
}

function setMode(rec, mode) {
  rec.mode = mode;
  rec.modeTag.textContent = mode === 'RAG' ? '· Legal RAG' : mode === 'LLM' ? '· General' : '';
}

function finishAssistant(rec, answer, note) {
  rec.answer = answer;
  if (rec.mode) setMode(rec, rec.mode);
  rec.body.classList.remove('streaming');
  renderMarkdown(rec.body, answer, { maxCite: rec.sources.length });
  rec.col.querySelector('.msg-actions')?.remove();
  rec.col.querySelector('.msg-note')?.remove();
  if (note) rec.col.append(el('div', 'msg-note', note));
  const actions = el('div', 'msg-actions');
  const copy = iconButton('copy', 'Copy answer');
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(plainAnswer(rec.answer));
      copy.innerHTML = ICONS.check;
      toast('Answer copied');
      setTimeout(() => { copy.innerHTML = ICONS.copy; }, 1400);
    } catch { toast('Copy failed — select the text instead.'); }
  });
  actions.append(copy);
  if (rec.question) {
    const retry = iconButton('retry', 'Regenerate answer');
    retry.addEventListener('click', () => { if (!busy) send(rec.question, { replace: rec }); });
    actions.append(retry);
  }
  if (rec.sources.length) {
    const src = el('button', 'btn btn-ghost');
    src.type = 'button';
    src.innerHTML = ICONS.book; // static icon
    src.append(document.createTextNode(`${rec.sources.length} sources`));
    src.addEventListener('click', () => { showEvidence(rec); setEvidence(true, { focus: true }); });
    actions.append(src);
  }
  rec.col.append(actions);
}

function showError(rec, message) {
  rec.body.replaceChildren();
  rec.col.querySelector('.msg-actions')?.remove();
  const box = el('div', 'msg-error');
  box.setAttribute('role', 'alert');
  box.append(el('span', null, message));
  const retry = el('button', 'btn btn-secondary', 'Retry');
  retry.type = 'button';
  retry.style.height = '28px';
  retry.addEventListener('click', () => { if (!busy) send(rec.question, { replace: rec }); });
  box.append(retry);
  rec.body.append(box);
}

// Citation clicks (event delegation)
messagesEl.addEventListener('click', (e) => {
  const cite = e.target.closest('.cite');
  if (!cite) return;
  const rec = thread.find((r) => r.row.contains(cite));
  if (!rec) return;
  showEvidence(rec, Number(cite.dataset.cite));
  setEvidence(true, { focus: false });
  messagesEl.querySelectorAll('.cite.active').forEach((c) => c.classList.remove('active'));
  cite.classList.add('active');
});

// Hovering a citation highlights its source when that answer's sources are on screen.
messagesEl.addEventListener('mouseover', (e) => peekSource(e.target.closest('.cite'), true));
messagesEl.addEventListener('mouseout', (e) => peekSource(e.target.closest('.cite'), false));
messagesEl.addEventListener('focusin', (e) => peekSource(e.target.closest('.cite'), true));
messagesEl.addEventListener('focusout', (e) => peekSource(e.target.closest('.cite'), false));
function peekSource(cite, on) {
  if (!cite) return;
  const rec = thread.find((r) => r.row.contains(cite));
  if (!rec || rec !== shownRec) return;
  document.getElementById(`src-${cite.dataset.cite}`)?.classList.toggle('peek', on);
}

/* ================= Evidence panel ================= */
let shownRec = null;
function showEvidencePending() {
  shownRec = null;
  evidenceCount.hidden = true;
  evidenceBody.replaceChildren(el('p', 'evidence-empty', 'Retrieving passages for this question…'));
}

function showEvidence(rec, highlight) {
  const same = rec && rec === shownRec && evidenceBody.childElementCount === (rec.sources || []).length;
  shownRec = rec;
  const sources = rec?.sources || [];
  evidenceCount.hidden = sources.length === 0;
  evidenceCount.textContent = String(sources.length);
  // The toggle only exists while there is evidence to open.
  toggleEvidenceBtn.hidden = sources.length === 0;
  evidenceBody.replaceChildren();
  if (!sources.length) {
    const p = el('p', 'evidence-empty');
    p.textContent = 'Retrieved legal passages appear here for legal questions. Click a numbered citation in an answer to jump to its source.';
    evidenceBody.append(p);
    return;
  }
  for (const s of sources) {
    const card = el('article', 'source-card');
    card.id = `src-${s.id}`;
    card.setAttribute('aria-label', `Source ${s.id}`);
    const head = el('div', 'source-head');
    head.append(el('span', 'source-num', String(s.id)));
    const info = el('div', 'min-w-0');
    info.append(el('div', 'source-title' + (s.title ? '' : ' untitled'), s.title || 'Untitled passage (no document metadata)'));
    // Only metadata the index actually recorded; nothing is inferred here.
    const meta = el('div', 'source-meta');
    if (s.section) meta.append(el('span', 'badge', `${s.section_kind || 'Section'} ${s.section}`));
    if (s.page) meta.append(el('span', 'badge', s.page_end ? `pp. ${s.page}–${s.page_end}` : `p. ${s.page}`));
    if (s.cited) meta.append(el('span', 'badge', 'Cited'));
    if (meta.childElementCount) info.append(meta);
    if (s.section_title) info.append(el('div', 't-meta', s.section_title));
    if (s.note) info.append(el('div', 'badge badge-note', s.note));
    head.append(info);
    // Chunks from the rebuilt index start with a context line ("<Document> — Section N (...)")
    // that the model sees; the panel already shows it as title + badges.
    let body = (s.text || '').replace(/[ \t]+/g, ' ').trim();
    if (s.title && body.startsWith(s.title)) body = body.slice(body.indexOf('\n') + 1 || body.length).trim();
    const text = el('p', 'source-text', body);
    card.append(head, text);
    if ((s.text || '').length > 320) {
      const more = el('button', 'source-toggle', 'Show full passage');
      more.type = 'button';
      more.setAttribute('aria-expanded', 'false');
      more.addEventListener('click', () => {
        const open = card.classList.toggle('expanded');
        more.textContent = open ? 'Show less' : 'Show full passage';
        more.setAttribute('aria-expanded', String(open));
      });
      card.append(more);
    }
    evidenceBody.append(card);
  }
  if (!same && window.gsap && !reduceMotion()) {
    evidenceBody.querySelectorAll('.source-card').forEach((c) => { c.style.animation = 'none'; });
    window.gsap.from(evidenceBody.querySelectorAll('.source-card'),
      { opacity: 0, y: 8, duration: 0.25, stagger: 0.04, ease: 'power2.out', clearProps: 'opacity,transform' });
  }
  if (highlight) {
    const card = $(`src-${highlight}`);
    if (card) {
      card.classList.add('highlight', 'expanded');
      card.scrollIntoView({ block: 'nearest', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
      setTimeout(() => card.classList.remove('highlight'), 1600);
    }
  }
}

/* ================= Persistence ================= */
async function ensureChat(firstMessage) {
  if (currentChatId) return currentChatId;
  const title = firstMessage.slice(0, 60) + (firstMessage.length > 60 ? '…' : '');
  const { data, error } = await supabase.from('chats').insert({ user_id: session.user.id, title }).select().single();
  if (error) throw error;
  currentChatId = data.id;
  titleEl.textContent = title;
  chats.unshift(data);
  renderChatList();
  return currentChatId;
}

async function persistMessage(role, content, sources) {
  if (!currentChatId) return null;
  const row = { chat_id: currentChatId, role, content };
  if (sources && sourcesColumn) {
    const { data, error } = await supabase.from('messages').insert({ ...row, sources }).select('id').single();
    if (!error) return data.id;
    // Older schema without a `sources` column: store the answer text only.
    if (/sources/i.test(error.message || '') || error.code === 'PGRST204' || error.code === '42703') sourcesColumn = false;
    else { console.error(error); return null; }
  }
  const { data, error } = await supabase.from('messages').insert(row).select('id').single();
  if (error) { console.error(error); return null; }
  return data.id;
}

/* ================= Send ================= */
async function send(text, { replace } = {}) {
  hideEmptyState();
  let rec;
  if (replace) {
    rec = replace;
    rec.sources = [];
  } else {
    addUser(text);
    rec = addAssistant(text);
  }
  showThinking(rec);
  scrollToBottom(true);
  setBusy(true);
  controller = new AbortController();
  const chatAtStart = currentChatId;
  const seq = ++requestSeq;
  const current = () => seq === requestSeq && thread.includes(rec);
  // Never leave the previous answer's passages on screen while this one is pending.
  if (evidenceOpen()) showEvidencePending(); else showEvidence(null);

  try {
    if (!replace) {
      await ensureChat(text);
      await persistMessage('user', text);
    }
  } catch (err) {
    console.error(err);
    toast('Could not save this conversation; the answer will not be stored.');
  }

  let raw = '';
  let frame = 0;
  const paint = () => {
    frame = 0;
    rec.body.classList.add('streaming');
    renderMarkdown(rec.body, raw, { maxCite: rec.sources.length });
    scrollToBottom();
  };
  try {
    const final = await streamAsk(text, {
      signal: controller.signal,
      onSources: (sources, mode) => {
        if (!current()) return;
        setMode(rec, mode);
        if (mode === 'RAG' && sources.length) {
          rec.sources = sources;
          showEvidence(rec);
          if (mqDesktop.matches) setEvidence(true);
        } else {
          rec.sources = [];
          clearEvidence();
        }
      },
      onToken: (t) => { if (!current()) return; raw += t; if (!frame) frame = requestAnimationFrame(paint); },
    });
    cancelAnimationFrame(frame);
    if (!current()) return;
    if (final.mode) setMode(rec, final.mode);
    rec.sources = rec.mode === 'RAG' ? (final.sources || rec.sources) : [];
    finishAssistant(rec, final.answer);
    if (rec.sources.length) showEvidence(rec); else clearEvidence();
    announce('Answer ready');
    if (currentChatId === chatAtStart || !chatAtStart) await saveAnswer(rec, final.answer, replace);
  } catch (err) {
    cancelAnimationFrame(frame);
    if (!current()) return;
    if (err.name === 'AbortError') {
      if (raw.trim()) {
        finishAssistant(rec, raw, 'Generation stopped.');
        await saveAnswer(rec, raw, replace);
      } else {
        showError(rec, 'Generation stopped.');
      }
      announce('Generation stopped');
    } else {
      showError(rec, err.message || 'Something went wrong.');
      if (shownRec === null || shownRec === rec) clearEvidence();
      announce('The answer failed');
    }
  } finally {
    controller = null;
    setBusy(false);
    scrollToBottom();
  }
}

async function saveAnswer(rec, answer, replaced) {
  const oldId = replaced ? rec.rowId : null;
  rec.rowId = await persistMessage('assistant', answer, rec.sources);
  if (oldId && rec.rowId) await supabase.from('messages').delete().eq('id', oldId);
}
