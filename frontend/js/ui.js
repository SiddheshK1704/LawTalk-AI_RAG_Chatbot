// Landing page: masthead, Justice Orb sign-in/sign-up, session-aware CTAs, motion.
// Supabase calls and redirects are unchanged from the original (see auth.js).
import { login, signup, onAuthChange, getSession, logout } from './auth.js';
import { initThemeToggles } from './theme.js';

initThemeToggles();

const $ = (id) => document.getElementById(id);
const gsap = window.gsap;
const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const animate = () => Boolean(gsap) && !reduceMotion();

const modal = $('authModal');
const orb = $('orb');
const flipper = orb.querySelector('.orb-flipper');
const bubble = modal.querySelector('.orb-bubble');
const backdrop = modal.querySelector('.orb-backdrop');
const faces = { login: $('loginFace'), signup: $('signupFace') };
const loginBtn = $('openLogin');
const startBtns = [...document.querySelectorAll('[data-start]')];
const pageRegions = [document.querySelector('.masthead'), $('main'), document.querySelector('.footer')];

let currentSession = null;
let opener = null;
let side = 'login';
let openTl = null;

/* ================= Forms: validation and submit ================= */
const FORMS = {
  login: { form: $('loginForm'), email: $('loginEmail'), password: $('loginPassword'), message: $('loginMessage'),
           submit: $('loginSubmit'), label: 'Log in', busy: 'Signing in…' },
  signup: { form: $('signupForm'), email: $('signupEmail'), password: $('signupPassword'), message: $('signupMessage'),
            submit: $('signupSubmit'), label: 'Create account', busy: 'Creating account…' },
};

function setFieldError(input, text) {
  const err = $(`${input.id}Error`);
  err.textContent = text || '';
  err.hidden = !text;
  if (text) input.setAttribute('aria-invalid', 'true'); else input.removeAttribute('aria-invalid');
}
function validateEmail(input) {
  const v = input.value.trim();
  const msg = !v ? 'Enter your email address.' : !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? 'Enter a valid email address.' : '';
  setFieldError(input, msg);
  return !msg;
}
function validatePassword(input) {
  const v = input.value;
  const msg = !v ? 'Enter your password.' : v.length < 6 ? 'Password must be at least 6 characters.' : '';
  setFieldError(input, msg);
  return !msg;
}
function showMessage(f, text, ok = false) {
  f.message.textContent = text;
  f.message.classList.toggle('success', ok);
  f.message.hidden = false;
}
function resetForm(f) {
  f.form.reset();
  f.message.hidden = true;
  setFieldError(f.email, '');
  setFieldError(f.password, '');
  f.password.type = 'password';
}

// Supabase error text -> clearer wording (unknown errors are shown as-is).
function friendlyError(err) {
  const m = (err?.message || '').toLowerCase();
  if (m.includes('invalid login credentials')) return 'Incorrect email or password.';
  if (m.includes('email not confirmed')) return 'Please confirm your email first. Check your inbox for the link.';
  if (m.includes('already registered') || m.includes('already exists')) return 'An account with this email already exists. Log in instead.';
  if (m.includes('rate limit') || m.includes('too many')) return 'Too many attempts. Please wait a moment and try again.';
  if (m.includes('failed to fetch') || m.includes('network')) return 'Could not reach the server. Check your connection.';
  return err?.message || 'Something went wrong. Please try again.';
}

function setBusy(f, busy) {
  f.submit.disabled = busy;
  f.submit.querySelector('.spinner').hidden = !busy;
  f.submit.querySelector('.submit-label').textContent = busy ? f.busy : f.label;
  f.submit.setAttribute('aria-busy', String(busy));
}

for (const [name, f] of Object.entries(FORMS)) {
  f.email.addEventListener('blur', () => { if (f.email.value) validateEmail(f.email); });
  f.password.addEventListener('blur', () => { if (f.password.value) validatePassword(f.password); });
  f.email.addEventListener('input', () => { if (f.email.hasAttribute('aria-invalid')) validateEmail(f.email); f.message.hidden = true; });
  f.password.addEventListener('input', () => { if (f.password.hasAttribute('aria-invalid')) validatePassword(f.password); f.message.hidden = true; });
  f.form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (f.submit.disabled) return;
    f.message.hidden = true;
    const okEmail = validateEmail(f.email);
    const okPassword = validatePassword(f.password);
    if (!okEmail || !okPassword) { (okEmail ? f.password : f.email).focus(); return; }
    const email = f.email.value.trim();
    const password = f.password.value;
    setBusy(f, true);
    try {
      if (name === 'login') {
        await login(email, password);
        window.location.href = 'chat.html';
        return;
      }
      const data = await signup(email, password);
      // With email confirmation on, Supabase returns a user with no identities (instead of
      // an error) when the address is already registered.
      if (data?.user && Array.isArray(data.user.identities) && data.user.identities.length === 0) {
        showMessage(f, 'An account with this email already exists. Log in instead.');
        return;
      }
      resetForm(f);
      FORMS.login.email.value = email;
      await flipTo('login');
      showMessage(FORMS.login, 'Account created. Check your email to confirm, then log in.', true);
    } catch (err) {
      showMessage(f, friendlyError(err));
    } finally {
      setBusy(f, false);
    }
  });
}

document.querySelectorAll('[data-toggle-password]').forEach((btn) => btn.addEventListener('click', () => {
  const input = $(btn.dataset.togglePassword);
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  btn.setAttribute('aria-pressed', String(show));
  btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  btn.querySelector('.eye-open').hidden = show;
  btn.querySelector('.eye-closed').hidden = !show;
  input.focus();
}));

/* ================= Justice Orb: open / flip / close ================= */
function setSide(next) {
  side = next;
  faces.login.inert = next !== 'login';
  faces.signup.inert = next !== 'signup';
  orb.setAttribute('aria-labelledby', next === 'login' ? 'loginTitle' : 'signupTitle');
}

function flipTo(next) {
  if (next === side) return Promise.resolve();
  setSide(next);
  const focusFirst = () => FORMS[next].email.focus();
  if (!animate()) {
    flipper.style.transform = next === 'signup' ? 'rotateY(180deg)' : '';
    focusFirst();
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    gsap.to(flipper, { rotationY: next === 'signup' ? 180 : 0, duration: 0.6, ease: 'power2.inOut',
      onComplete: () => { focusFirst(); resolve(); } });
  });
}
$('toSignup').addEventListener('click', () => { FORMS.login.message.hidden = true; flipTo('signup'); });
$('toLogin').addEventListener('click', () => { FORMS.signup.message.hidden = true; flipTo('login'); });

function focusables() {
  return [...faces[side].querySelectorAll('button, [href], input')].filter((el) => !el.disabled && el.offsetParent !== null);
}
function onKeydown(e) {
  if (e.key === 'Escape') { e.preventDefault(); closeModal(); return; }
  if (e.key !== 'Tab') return;
  const items = focusables();
  if (!items.length) return;
  const first = items[0], last = items[items.length - 1];
  if (!faces[side].contains(document.activeElement)) { e.preventDefault(); first.focus(); }
  else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}

function buildOpenTimeline(from) {
  // 1) a small bubble appears at the button, 2) travels to the centre, 3) the orb grows out of it.
  const r = from?.getBoundingClientRect?.();
  const startX = r ? r.left + r.width / 2 - window.innerWidth / 2 : 0;
  const startY = r ? r.top + r.height / 2 - window.innerHeight / 2 : -window.innerHeight / 3;
  const items = faces.login.querySelectorAll('.orb-item, .orb-close');
  const tl = gsap.timeline({ paused: true, defaults: { ease: 'power3.out' } });
  tl.set(orb, { clipPath: 'circle(0px at 50% 50%)' })
    .set(items, { autoAlpha: 0, y: 8 })
    .fromTo(backdrop, { opacity: 0 }, { opacity: 1, duration: 0.35, ease: 'power1.out' }, 0)
    .fromTo(bubble, { x: startX, y: startY, scale: 0.4, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.14 }, 0)
    .to(bubble, { x: 0, y: 0, duration: 0.5, ease: 'power2.inOut' }, 0.08)
    .to(orb, { clipPath: 'circle(72% at 50% 50%)', duration: 0.5, ease: 'power3.inOut' }, 0.5)
    .to(bubble, { scale: 3, opacity: 0, duration: 0.3, ease: 'power1.out' }, 0.52)
    .to(items, { autoAlpha: 1, y: 0, duration: 0.3, stagger: 0.03 }, 0.82);
  return tl;
}

function openModal(fromEl = document.activeElement) {
  if (!modal.hidden) return;
  opener = fromEl;
  closeMenu(false);
  resetForm(FORMS.login);
  resetForm(FORMS.signup);
  setSide('login');
  flipper.style.transform = '';
  if (gsap) gsap.set(flipper, { rotationY: 0 });
  modal.hidden = false;
  document.body.classList.add('modal-open');
  pageRegions.forEach((el) => { if (el) el.inert = true; });  // background cannot be reached
  document.addEventListener('keydown', onKeydown);
  if (animate()) {
    openTl = buildOpenTimeline(fromEl);
    openTl.eventCallback('onComplete', () => FORMS.login.email.focus());
    openTl.play(0);
  } else {
    openTl = null;
    FORMS.login.email.focus();
  }
}

function closeModal() {
  if (modal.hidden) return;
  document.removeEventListener('keydown', onKeydown);
  const finish = () => {
    modal.hidden = true;
    document.body.classList.remove('modal-open');
    pageRegions.forEach((el) => { if (el) el.inert = false; });
    if (gsap) gsap.set([orb, bubble, backdrop, flipper, ...faces.login.querySelectorAll('.orb-item, .orb-close')], { clearProps: 'all' });
    flipper.style.transform = '';
    opener?.focus?.();
  };
  if (openTl && animate()) {
    // Reverse the entrance: flip back to the front first if needed, then retract into the bubble.
    const reverse = () => { openTl.eventCallback('onReverseComplete', finish); openTl.timeScale(1.6).reverse(); };
    if (side === 'signup') { setSide('login'); gsap.to(flipper, { rotationY: 0, duration: 0.35, ease: 'power2.inOut', onComplete: reverse }); }
    else reverse();
  } else {
    finish();
  }
}
modal.querySelectorAll('[data-close-modal]').forEach((el) => el.addEventListener('click', closeModal));

/* ================= CTAs (same behaviour as before) ================= */
loginBtn.addEventListener('click', (e) => {
  if (currentSession) { logout(); return; }
  openModal(e.currentTarget);
});
startBtns.forEach((b) => b.addEventListener('click', (e) => {
  closeMenu(false);
  if (currentSession) window.location.href = 'chat.html';
  else openModal(e.currentTarget);
}));

/* ================= Session-aware labels ================= */
async function refreshNav() {
  currentSession = await getSession();
  loginBtn.textContent = currentSession ? 'Log out' : 'Log in';
  document.querySelector('[data-menu-login]').textContent = currentSession ? 'Log out' : 'Log in';
  document.querySelectorAll('.start-label').forEach((s) => { s.textContent = currentSession ? 'Continue researching' : 'Start researching'; });
}
onAuthChange((session) => { currentSession = session; refreshNav(); });
refreshNav();

/* ================= Masthead: scroll state, active section, mobile menu ================= */
const masthead = $('masthead');
const onScroll = () => masthead.classList.toggle('scrolled', window.scrollY > 8);
window.addEventListener('scroll', onScroll, { passive: true });
onScroll();

const navLinks = [...document.querySelectorAll('.nav-links a[href^="#"]')];
if ('IntersectionObserver' in window) {
  const io = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (!en.isIntersecting) return;
      navLinks.forEach((a) => {
        const on = a.getAttribute('href') === `#${en.target.id}`;
        a.classList.toggle('active', on);
        if (on) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
      });
    });
  }, { rootMargin: '-45% 0px -50% 0px' });
  ['product', 'how', 'features'].forEach((id) => { const el = $(id); if (el) io.observe(el); });
}

const menuBtn = $('menuBtn');
const menu = $('mobileMenu');
function openMenu() {
  menu.hidden = false;
  menuBtn.setAttribute('aria-expanded', 'true');
  menuBtn.setAttribute('aria-label', 'Close menu');
  if (animate()) gsap.from(menu, { opacity: 0, y: -4, duration: 0.18, ease: 'power2.out', clearProps: 'all' });
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
menu.querySelector('[data-menu-login]').addEventListener('click', (e) => {
  closeMenu(false);
  if (currentSession) logout(); else openModal(menuBtn);
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !menu.hidden && modal.hidden) closeMenu(); });
document.addEventListener('click', (e) => {
  if (!menu.hidden && !menu.contains(e.target) && !menuBtn.contains(e.target)) closeMenu(false);
});

/* ================= Research-status label (reacts to the CTAs; no fake data) ================= */
const status = document.querySelector('.status');
const statusText = $('heroStatus');
document.querySelectorAll('[data-status]').forEach((el) => {
  const on = () => { statusText.textContent = el.dataset.status; status.classList.add('active'); };
  const off = () => { statusText.textContent = statusText.dataset.default; status.classList.remove('active'); };
  el.addEventListener('mouseenter', on); el.addEventListener('focus', on);
  el.addEventListener('mouseleave', off); el.addEventListener('blur', off);
});

/* ================= Motion (GSAP) ================= */
(function motion() {
  const root = document.documentElement;
  if (!animate()) { root.classList.remove('motion'); return; }
  if (window.ScrollTrigger) gsap.registerPlugin(window.ScrollTrigger);

  gsap.fromTo('[data-reveal="hero"]', { autoAlpha: 0, y: 16 },
    { autoAlpha: 1, y: 0, duration: 0.7, ease: 'power3.out', stagger: 0.08, delay: 0.05 });
  gsap.fromTo('[data-reveal="lady"]', { autoAlpha: 0, y: 12 },
    { autoAlpha: 1, y: 0, duration: 1.0, ease: 'power2.out', delay: 0.2 });

  // Section reveals: restrained opacity/translate as each block enters, once.
  if (window.ScrollTrigger) {
    gsap.utils.toArray('[data-reveal=""]').forEach((el) => {
      gsap.from(el, { opacity: 0, y: 14, duration: 0.6, ease: 'power2.out', scrollTrigger: { trigger: el, start: 'top 88%', once: true } });
    });
  }

  // The artwork answers the pointer very slightly (max 6px), mouse/trackpad only.
  if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
  const hero = document.querySelector('.hero');
  const lady = document.querySelector('.lady');
  const lx = gsap.quickTo(lady, 'x', { duration: 0.9, ease: 'power3.out' });
  const ly = gsap.quickTo(lady, 'y', { duration: 0.9, ease: 'power3.out' });
  hero.addEventListener('pointermove', (e) => {
    const r = hero.getBoundingClientRect();
    const dx = Math.max(-1, Math.min(1, ((e.clientX - r.left) / r.width) * 2 - 1));
    const dy = Math.max(-1, Math.min(1, ((e.clientY - r.top) / r.height) * 2 - 1));
    lx(dx * 6); ly(dy * 6);
  });
  hero.addEventListener('pointerleave', () => { lx(0); ly(0); });
})();
