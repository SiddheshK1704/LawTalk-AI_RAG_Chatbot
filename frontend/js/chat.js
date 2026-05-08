// Chat page logic: history, send, persist
import { supabase } from './supabase.js';
import { requireAuth, logout, onAuthChange } from './auth.js';
import { askAI } from './api.js';

const messagesEl = document.getElementById('messages');
const emptyState = document.getElementById('emptyState');
const form = document.getElementById('chatForm');
const input = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const newChatBtn = document.getElementById('newChatBtn');
const chatListEl = document.getElementById('chatList');
const titleEl = document.getElementById('chatTitle');
const userEmailEl = document.getElementById('userEmail');
const avatarEl = document.getElementById('userAvatar');
const logoutBtn = document.getElementById('logoutBtn');
const sidebar = document.getElementById('sidebar');
const openSidebarBtn = document.getElementById('openSidebar');
const closeSidebarBtn = document.getElementById('closeSidebar');

let session = null;
let currentChatId = null;

// Init
(async () => {
  session = await requireAuth();
  if (!session) return;
  const user = session.user;
  userEmailEl.textContent = user.email;
  avatarEl.textContent = (user.email?.[0] || 'U').toUpperCase();
  await loadChats();
})();

logoutBtn?.addEventListener('click', () => logout());
onAuthChange((s) => { if (!s) window.location.href = 'index.html'; });

openSidebarBtn?.addEventListener('click', () => sidebar.classList.remove('-translate-x-full'));
closeSidebarBtn?.addEventListener('click', () => sidebar.classList.add('-translate-x-full'));

newChatBtn.addEventListener('click', () => startNewChat());

input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 160) + 'px';
});
input.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  input.style.height = 'auto';
  await sendMessage(text);
});

function startNewChat() {
  currentChatId = null;
  titleEl.textContent = 'New Conversation';
  messagesEl.innerHTML = '';
  messagesEl.appendChild(emptyState);
  emptyState.style.display = '';
  document.querySelectorAll('.chat-item').forEach(c => c.classList.remove('active'));
}

async function loadChats() {
  const { data, error } = await supabase
    .from('chats')
    .select('*')
    .eq('user_id', session.user.id)
    .order('created_at', { ascending: false });
  if (error) { console.error(error); return; }
  renderChatList(data || []);
}

function renderChatList(chats) {
  chatListEl.innerHTML = '';
  if (!chats.length) {
    chatListEl.innerHTML = '<div class="text-white/40 text-xs px-1">No chats yet</div>';
    return;
  }
  chats.forEach(c => {
    const div = document.createElement('div');
    div.className = 'chat-item' + (c.id === currentChatId ? ' active' : '');
    div.dataset.id = c.id;

    const title = document.createElement('span');
    title.className = 'chat-item-title';
    title.textContent = c.title || 'Untitled';
    title.title = c.title || '';
    title.addEventListener('click', () => openChat(c));

    const del = document.createElement('button');
    del.className = 'chat-delete';
    del.title = 'Delete chat';
    del.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/></svg>';
    del.addEventListener('click', (e) => {
      e.stopPropagation();
      deleteChat(c);
    });

    div.appendChild(title);
    div.appendChild(del);
    chatListEl.appendChild(div);
  });
}

async function deleteChat(chat) {
  if (!confirm(`Delete "${chat.title || 'this chat'}"? This cannot be undone.`)) return;

  // 1) Delete messages first (in case the FK has no ON DELETE CASCADE)
  const { error: msgErr, count: msgCount } = await supabase
    .from('messages')
    .delete({ count: 'exact' })
    .eq('chat_id', chat.id);
  console.log('[deleteChat] messages deleted:', msgCount, 'error:', msgErr);
  if (msgErr) {
    alert('Failed to delete messages: ' + msgErr.message +
      '\n\nLikely an RLS policy on the messages table. See console.');
    return;
  }

  // 2) Delete the chat row
  const { error: chatErr, count: chatCount } = await supabase
    .from('chats')
    .delete({ count: 'exact' })
    .eq('id', chat.id)
    .eq('user_id', session.user.id);
  console.log('[deleteChat] chats deleted:', chatCount, 'error:', chatErr);
  if (chatErr) {
    alert('Failed to delete chat: ' + chatErr.message);
    return;
  }
  if (chatCount === 0) {
    alert('Chat was not deleted (0 rows affected). Likely an RLS policy on the chats table is blocking DELETE for this user.');
    return;
  }

  if (currentChatId === chat.id) startNewChat();
  await loadChats();
}

async function openChat(chat) {
  currentChatId = chat.id;
  titleEl.textContent = chat.title;
  emptyState.style.display = 'none';
  messagesEl.innerHTML = '';
  document.querySelectorAll('.chat-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === chat.id);
  });
  const { data } = await supabase
    .from('messages')
    .select('*')
    .eq('chat_id', chat.id)
    .order('created_at', { ascending: true });
  (data || []).forEach(m => addBubble(m.role, m.content, false));
  scrollToBottom();
  if (window.innerWidth < 768) sidebar.classList.add('-translate-x-full');
}

async function ensureChat(firstMessage) {
  if (currentChatId) return currentChatId;
  const title = firstMessage.slice(0, 60) + (firstMessage.length > 60 ? '…' : '');
  const { data, error } = await supabase
    .from('chats')
    .insert({ user_id: session.user.id, title })
    .select()
    .single();
  if (error) throw error;
  currentChatId = data.id;
  titleEl.textContent = title;
  await loadChats();
  return currentChatId;
}

async function persistMessage(role, content) {
  if (!currentChatId) return;
  await supabase.from('messages').insert({
    chat_id: currentChatId, role, content
  });
}

async function sendMessage(text) {
  emptyState.style.display = 'none';
  addBubble('user', text);
  scrollToBottom();
  sendBtn.disabled = true;

  try {
    await ensureChat(text);
    await persistMessage('user', text);

    const typingEl = addTyping();
    scrollToBottom();

    const reply = await askAI(text);
    typingEl.remove();
    addBubble('assistant', reply);
    scrollToBottom();
    await persistMessage('assistant', reply);
  } catch (err) {
    addBubble('assistant', '⚠️ ' + (err.message || 'Failed to get a response.'));
  } finally {
    sendBtn.disabled = false;
  }
}

function addBubble(role, content, animate = true) {
  const wrapper = document.createElement('div');
  wrapper.className = 'flex';
  const bubble = document.createElement('div');
  bubble.className = 'bubble ' + (role === 'user' ? 'bubble-user' : 'bubble-ai');
  if (role === 'assistant') {
    // Backend returns HTML-formatted answer (h2/p/ul/li/strong). Render it.
    bubble.innerHTML = sanitizeHtml(content ?? '');
  } else {
    bubble.textContent = content ?? '';
  }
  wrapper.appendChild(bubble);
  if (!animate) bubble.style.animation = 'none';
  messagesEl.appendChild(wrapper);
  return wrapper;
}

// Minimal sanitizer: allow a small set of formatting tags, strip everything else.
function sanitizeHtml(html) {
  const allowed = new Set(['H1','H2','H3','H4','P','UL','OL','LI','STRONG','B','EM','I','BR','CODE','PRE','BLOCKQUOTE','A','SPAN','DIV']);
  const tpl = document.createElement('template');
  tpl.innerHTML = String(html);
  const walk = (node) => {
    [...node.childNodes].forEach(child => {
      if (child.nodeType === 1) {
        if (!allowed.has(child.tagName)) {
          // unwrap disallowed tag
          while (child.firstChild) node.insertBefore(child.firstChild, child);
          node.removeChild(child);
          return;
        }
        // strip all attributes except href on <a>
        [...child.attributes].forEach(a => {
          if (!(child.tagName === 'A' && a.name === 'href')) child.removeAttribute(a.name);
        });
        if (child.tagName === 'A') {
          child.setAttribute('target', '_blank');
          child.setAttribute('rel', 'noopener noreferrer');
        }
        walk(child);
      }
    });
  };
  walk(tpl.content);
  return tpl.innerHTML;
}

function addTyping() {
  const wrapper = document.createElement('div');
  wrapper.className = 'flex';
  wrapper.innerHTML = `<div class="bubble bubble-ai"><div class="typing"><span></span><span></span><span></span></div></div>`;
  messagesEl.appendChild(wrapper);
  return wrapper;
}

function scrollToBottom() {
  messagesEl.scrollTo({ top: messagesEl.scrollHeight, behavior: 'smooth' });
}
