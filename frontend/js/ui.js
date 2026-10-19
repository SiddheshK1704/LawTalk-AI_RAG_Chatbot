// Landing page: auth modal, session-aware CTAs, theme toggle.
// Supabase calls and redirects are unchanged from the original (see auth.js).
import { login, signup, onAuthChange, getSession, logout } from './auth.js';
import { initThemeToggles } from './theme.js';

initThemeToggles();

const $ = (id) => document.getElementById(id);
const modal = $('authModal');
const card = modal.querySelector('.auth-card');
const segmented = modal.querySelector('.segmented');
const tabs = [...modal.querySelectorAll('.auth-tab')];
const form = $('authForm');
const emailEl = $('authEmail');
const passwordEl = $('authPassword');
const submitBtn = $('authSubmit');
const submitLabel = $('authSubmitLabel');
const spinner = submitBtn.querySelector('.spinner');
const messageEl = $('authError');
const loginBtn = $('openLogin');
const signupBtn = $('openSignup');
const startBtns = [...document.querySelectorAll('[data-start]')];

let mode = 'login';
let currentSession = null;
let opener = null;
let busy = false;

const COPY = {
  login: { title: 'Welcome back', sub: 'Sign in to your legal research workspace', submit: 'Sign in', busy: 'Signing in…' },
  signup: { title: 'Create your account', sub: 'Start your legal research workspace', submit: 'Create account', busy: 'Creating account…' },
};

/* ---------- Messages & validation ---------- */
function showMessage(text, ok = false) {
  messageEl.textContent = text;
  messageEl.classList.toggle('success', ok);
  messageEl.hidden = false;
}
function hideMessage() { messageEl.hidden = true; }

function setFieldError(input, errorEl, text) {
  errorEl.textContent = text || '';
  errorEl.hidden = !text;
  if (text) input.setAttribute('aria-invalid', 'true'); else input.removeAttribute('aria-invalid');
}
function validateEmail() {
  const v = emailEl.value.trim();
  const msg = !v ? 'Enter your email address.' : !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? 'Enter a valid email address.' : '';
  setFieldError(emailEl, $('emailError'), msg);
  return !msg;
}
function validatePassword() {
  const v = passwordEl.value;
  const msg = !v ? 'Enter your password.' : v.length < 6 ? 'Password must be at least 6 characters.' : '';
  setFieldError(passwordEl, $('passwordError'), msg);
  return !msg;
}
emailEl.addEventListener('blur', () => { if (emailEl.value) validateEmail(); });
passwordEl.addEventListener('blur', () => { if (passwordEl.value) validatePassword(); });
emailEl.addEventListener('input', () => { if (emailEl.hasAttribute('aria-invalid')) validateEmail(); hideMessage(); });
passwordEl.addEventListener('input', () => { if (passwordEl.hasAttribute('aria-invalid')) validatePassword(); hideMessage(); });

// Supabase error text -> clearer wording (unknown errors are shown as-is).
function friendlyError(err) {
  const m = (err?.message || '').toLowerCase();
  if (m.includes('invalid login credentials')) return 'Incorrect email or password.';
  if (m.includes('email not confirmed')) return 'Please confirm your email first. Check your inbox for the link.';
  if (m.includes('already registered') || m.includes('already exists')) return 'An account with this email already exists. Sign in instead.';
  if (m.includes('rate limit') || m.includes('too many')) return 'Too many attempts. Please wait a moment and try again.';
  if (m.includes('failed to fetch') || m.includes('network')) return 'Could not reach the server. Check your connection.';
  return err?.message || 'Something went wrong. Please try again.';
}

/* ---------- Mode (segmented toggle) ---------- */
function setMode(next, { animate = true } = {}) {
  if (next === mode && animate) return;
  mode = next;
  const apply = () => {
    const c = COPY[mode];
    $('authTitle').textContent = c.title;
    $('authSub').textContent = c.sub;
    submitLabel.textContent = c.submit;
    card.classList.remove('switching');
  };
  segmented.dataset.mode = mode;
  tabs.forEach((t) => {
    const on = t.dataset.tab === mode;
    t.setAttribute('aria-selected', String(on));
    t.tabIndex = on ? 0 : -1;
  });
  form.setAttribute('aria-labelledby', `tab-${mode}`);
  passwordEl.autocomplete = mode === 'login' ? 'current-password' : 'new-password';
  $('passwordHint').hidden = mode !== 'signup';
  setFieldError(emailEl, $('emailError'), '');
  setFieldError(passwordEl, $('passwordError'), '');
  if (animate && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    card.classList.add('switching');
    setTimeout(apply, 120);
  } else apply();
}
tabs.forEach((t) => t.addEventListener('click', () => { hideMessage(); setMode(t.dataset.tab); }));
segmented.addEventListener('keydown', (e) => {
  if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
  e.preventDefault();
  const next = mode === 'login' ? 'signup' : 'login';
  hideMessage();
  setMode(next);
  $(`tab-${next}`).focus();
});

/* ---------- Password visibility ---------- */
$('togglePassword').addEventListener('click', (e) => {
  const btn = e.currentTarget;
  const show = passwordEl.type === 'password';
  passwordEl.type = show ? 'text' : 'password';
  btn.setAttribute('aria-pressed', String(show));
  btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  btn.querySelector('.eye-open').hidden = show;
  btn.querySelector('.eye-closed').hidden = !show;
  passwordEl.focus();
});

/* ---------- Open / close with focus trap ---------- */
function focusables() {
  return [...card.querySelectorAll('button, [href], input, [tabindex]:not([tabindex="-1"])')]
    .filter((el) => !el.disabled && !el.hidden && el.offsetParent !== null);
}
function onKeydown(e) {
  if (e.key === 'Escape') { e.preventDefault(); closeModal(); return; }
  if (e.key !== 'Tab') return;
  const items = focusables();
  if (!items.length) return;
  const first = items[0], last = items[items.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  else if (!card.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
}

function openModal(initial = 'login', from = document.activeElement) {
  opener = from;
  hideMessage();
  setMode(initial, { animate: false });
  modal.hidden = false;
  document.body.classList.add('modal-open');
  void modal.offsetWidth; // start the transition from the hidden state
  modal.classList.add('open');
  document.addEventListener('keydown', onKeydown);
  setTimeout(() => emailEl.focus(), 30);
}

function closeModal() {
  if (modal.hidden) return;
  modal.classList.remove('open');
  document.removeEventListener('keydown', onKeydown);
  document.body.classList.remove('modal-open');
  const done = () => {
    modal.hidden = true;
    form.reset();
    passwordEl.type = 'password';
    setFieldError(emailEl, $('emailError'), '');
    setFieldError(passwordEl, $('passwordError'), '');
    hideMessage();
  };
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  setTimeout(done, reduce ? 0 : 220);
  opener?.focus?.();
}
modal.querySelectorAll('[data-close-modal]').forEach((el) => el.addEventListener('click', closeModal));

/* ---------- CTAs (same behaviour as before) ---------- */
loginBtn.addEventListener('click', (e) => {
  if (currentSession) { logout(); return; }
  openModal('login', e.currentTarget);
});
signupBtn.addEventListener('click', (e) => {
  if (currentSession) { window.location.href = 'chat.html'; return; }
  openModal('signup', e.currentTarget);
});
startBtns.forEach((b) => b.addEventListener('click', (e) => {
  closeMenu(false);
  if (currentSession) window.location.href = 'chat.html';
  else openModal('login', e.currentTarget);
}));

/* ---------- Submit ---------- */
function setBusy(v) {
  busy = v;
  submitBtn.disabled = v;
  spinner.hidden = !v;
  submitLabel.textContent = v ? COPY[mode].busy : COPY[mode].submit;
  submitBtn.setAttribute('aria-busy', String(v));
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (busy) return;
  hideMessage();
  const okEmail = validateEmail();
  const okPassword = validatePassword();
  if (!okEmail || !okPassword) { (okEmail ? passwordEl : emailEl).focus(); return; }
  const email = emailEl.value.trim();
  const password = passwordEl.value;
  setBusy(true);
  try {
    if (mode === 'login') {
      await login(email, password);
      window.location.href = 'chat.html';
      return;
    }
    const data = await signup(email, password);
    // With email confirmation on, Supabase returns a user with no identities
    // (instead of an error) when the address is already registered.
    if (data?.user && Array.isArray(data.user.identities) && data.user.identities.length === 0) {
      showMessage('An account with this email already exists. Sign in instead.');
      return;
    }
    setMode('login', { animate: false });
    showMessage('Account created! Check your email to confirm, then sign in.', true);
  } catch (err) {
    showMessage(friendlyError(err));
  } finally {
    setBusy(false);
  }
});

/* ---------- Session-aware nav ---------- */
async function refreshNav() {
  currentSession = await getSession();
  if (currentSession) {
    loginBtn.textContent = 'Log out';
    signupBtn.textContent = 'Open workspace';
    startBtns.forEach((b) => { b.textContent = 'Continue researching'; });
  } else {
    loginBtn.textContent = 'Log in';
    signupBtn.textContent = 'Sign up';
    startBtns.forEach((b) => { b.textContent = 'Start researching'; });
  }
}
onAuthChange((session) => { currentSession = session; refreshNav(); });
refreshNav();

/* ---------- Mobile menu ---------- */
const menuBtn = $('menuBtn');
const menu = $('mobileMenu');
function openMenu() {
  menu.hidden = false;
  menuBtn.setAttribute('aria-expanded', 'true');
  menuBtn.setAttribute('aria-label', 'Close menu');
  if (window.gsap && !reduceMotion()) window.gsap.from(menu, { opacity: 0, y: -6, duration: 0.18, ease: 'power2.out', clearProps: 'all' });
  menu.querySelector('a, button')?.focus();
}
function closeMenu(restoreFocus = true) {
  if (menu.hidden) return;
  menu.hidden = true;
  menuBtn.setAttribute('aria-expanded', 'false');
  menuBtn.setAttribute('aria-label', 'Open menu');
  if (restoreFocus) menuBtn.focus();
}
menuBtn.addEventListener('click', () => (menu.hidden ? openMenu() : closeMenu()));
menu.querySelectorAll('a').forEach((a) => a.addEventListener('click', () => closeMenu(false)));
menu.querySelector('[data-menu-login]').addEventListener('click', () => { closeMenu(false); loginBtn.click(); });
menu.querySelector('[data-menu-signup]').addEventListener('click', () => { closeMenu(false); signupBtn.click(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !menu.hidden && modal.hidden) closeMenu(); });
document.addEventListener('click', (e) => {
  if (!menu.hidden && !menu.contains(e.target) && !menuBtn.contains(e.target)) closeMenu(false);
});

/* ---------- Motion (GSAP) ---------- */
function reduceMotion() { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; }

(function motion() {
  const root = document.documentElement;
  if (!window.gsap || reduceMotion()) { root.classList.remove('motion'); return; }
  const gsap = window.gsap;
  if (window.ScrollTrigger) gsap.registerPlugin(window.ScrollTrigger);

  // Hero: text reveal, then Lady Justice fades in.
  gsap.fromTo('[data-reveal="hero"]', { autoAlpha: 0, y: 18 },
    { autoAlpha: 1, y: 0, duration: 0.7, ease: 'power3.out', stagger: 0.08, delay: 0.05 });
  gsap.fromTo('[data-reveal="lady"]', { autoAlpha: 0, x: 14 },
    { autoAlpha: 1, x: 0, duration: 1.1, ease: 'power2.out', delay: 0.2 });

  // Scroll reveals (each element once).
  if (window.ScrollTrigger) {
    gsap.utils.toArray('[data-reveal=""]').forEach((el) => {
      gsap.from(el, { opacity: 0, y: 16, duration: 0.6, ease: 'power2.out',
        scrollTrigger: { trigger: el, start: 'top 88%', once: true } });
    });
  }

  // Lady Justice follows the cursor a little (max 8px, smoothed); the glow follows less.
  if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
  const hero = document.querySelector('.hero');
  const lady = document.querySelector('.lady');
  const glow = document.querySelector('.art-glow');
  const lx = gsap.quickTo(lady, 'x', { duration: 0.8, ease: 'power3.out' });
  const ly = gsap.quickTo(lady, 'y', { duration: 0.8, ease: 'power3.out' });
  const gx = gsap.quickTo(glow, 'x', { duration: 1.2, ease: 'power3.out' });
  const gy = gsap.quickTo(glow, 'y', { duration: 1.2, ease: 'power3.out' });
  hero.addEventListener('pointermove', (e) => {
    const r = hero.getBoundingClientRect();
    const dx = Math.max(-1, Math.min(1, (e.clientX - r.left) / r.width * 2 - 1));
    const dy = Math.max(-1, Math.min(1, (e.clientY - r.top) / r.height * 2 - 1));
    lx(dx * 8); ly(dy * 8); gx(dx * 4); gy(dy * 4);
  });
  hero.addEventListener('pointerleave', () => { lx(0); ly(0); gx(0); gy(0); });
})();
