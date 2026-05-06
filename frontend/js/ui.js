// Landing page UI: dynamic island navbar, auth modal, session-aware CTAs
import { login, signup, onAuthChange, getSession, logout } from './auth.js';

/* ============= DYNAMIC ISLAND NAVBAR ============= */
const navbar = document.getElementById('navbar');
let collapseTimer;

function expandNav() {
  clearTimeout(collapseTimer);
  navbar?.classList.add('expanded');
}
function collapseNav() {
  collapseTimer = setTimeout(() => navbar?.classList.remove('expanded'), 200);
}

navbar?.addEventListener('mouseenter', expandNav);
navbar?.addEventListener('mouseleave', collapseNav);
navbar?.addEventListener('focusin', expandNav);
navbar?.addEventListener('focusout', collapseNav);
// On touch devices, tap toggles
navbar?.addEventListener('click', (e) => {
  if (window.matchMedia('(hover: none)').matches) {
    e.stopPropagation();
    navbar.classList.toggle('expanded');
  }
});
document.addEventListener('click', (e) => {
  if (navbar && !navbar.contains(e.target)) navbar.classList.remove('expanded');
});

/* ============= AUTH MODAL ============= */
const modal = document.getElementById('authModal');
const tabs = document.querySelectorAll('.auth-tab');
const titleEl = document.getElementById('authTitle');
const subEl = document.getElementById('authSub');
const submitBtn = document.getElementById('authSubmit');
const form = document.getElementById('authForm');
const errEl = document.getElementById('authError');
const loginBtn = document.getElementById('openLogin');
const signupBtn = document.getElementById('openSignup');
const startBtn = document.getElementById('startChatting');

let mode = 'login';
let currentSession = null;

function showError(msg, ok = false) {
  errEl.textContent = msg;
  errEl.style.display = 'block';
  errEl.classList.toggle('text-emerald-300', ok);
  errEl.classList.toggle('text-red-300', !ok);
}
function hideError() { errEl.style.display = 'none'; }

function openModal(initial = 'login') {
  setMode(initial);
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
}
function closeModal() {
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
  hideError();
  form.reset();
}
function setMode(next) {
  mode = next;
  tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === next));
  if (next === 'login') {
    titleEl.textContent = 'Welcome back';
    subEl.textContent = 'Sign in to continue your conversations.';
    submitBtn.textContent = 'Login';
  } else {
    titleEl.textContent = 'Create account';
    subEl.textContent = 'Join LawTalk AI in seconds.';
    submitBtn.textContent = 'Sign Up';
  }
  hideError();
}

loginBtn?.addEventListener('click', (e) => {
  e.stopPropagation();
  if (currentSession) { logout(); return; }
  openModal('login');
});
signupBtn?.addEventListener('click', () => {
  if (currentSession) { window.location.href = 'chat.html'; return; }
  openModal('signup');
});
startBtn?.addEventListener('click', () => {
  if (currentSession) {
    window.location.href = 'chat.html';
  } else {
    openModal('login');
  }
});

tabs.forEach(t => t.addEventListener('click', () => setMode(t.dataset.tab)));
document.querySelectorAll('[data-close-modal]').forEach(el =>
  el.addEventListener('click', closeModal)
);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && modal.classList.contains('open')) closeModal();
});

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  hideError();
  submitBtn.disabled = true;
  const originalText = mode === 'login' ? 'Login' : 'Sign Up';
  submitBtn.textContent = 'Please wait…';
  const email = document.getElementById('authEmail').value.trim();
  const password = document.getElementById('authPassword').value;
  try {
    if (mode === 'login') {
      await login(email, password);
      window.location.href = 'chat.html';
    } else {
      await signup(email, password);
      showError('Account created! Check your email to confirm, then login.', true);
      setMode('login');
    }
  } catch (err) {
    showError(err.message || 'Something went wrong.');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = originalText;
  }
});

/* ============= SESSION-AWARE NAV ============= */
async function refreshNav() {
  currentSession = await getSession();
  if (!loginBtn) return;
  if (currentSession) {
    loginBtn.textContent = 'Logout';
    if (signupBtn) signupBtn.textContent = 'Open Chat';
    if (startBtn) startBtn.textContent = 'Continue Chatting →';
  } else {
    loginBtn.textContent = 'Login / Sign Up';
    if (signupBtn) signupBtn.textContent = 'Create Account';
    if (startBtn) startBtn.textContent = 'Start Chatting →';
  }
}
onAuthChange((session) => {
  currentSession = session;
  refreshNav();
});
refreshNav();
