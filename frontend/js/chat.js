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
    div.textContent = c.title || 'Untitled';
    div.title = c.title;
    div.addEventListener('click', () => openChat(c));
    chatListEl.appendChild(div);
  });
}

async function openChat(chat) {
  currentChatId = chat.id;
  titleEl.textContent = chat.title;
  emptyState.style.display = 'none';
  messagesEl.innerHTML = '';
  document.querySelectorAll('.chat-item').forEach(el => {
    el.classList.toggle('active', el.textContent === chat.title);
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
  bubble.textContent = content;
  wrapper.appendChild(bubble);
  if (!animate) bubble.style.animation = 'none';
  messagesEl.appendChild(wrapper);
  return wrapper;
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
