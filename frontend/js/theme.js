// Light/dark theme with a circular reveal from the clicked toggle.
// The initial theme is set before first paint by an inline <head> script that
// reads the same storage key (see index.html / chat.html).
export const THEME_KEY = 'lawtalk-theme';

export function currentTheme() {
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
}

function apply(theme, persist = true) {
  document.documentElement.dataset.theme = theme;
  if (persist) {
    try { localStorage.setItem(THEME_KEY, theme); } catch { /* storage unavailable */ }
  }
  document.querySelectorAll('.theme-toggle').forEach((b) => {
    const label = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme';
    b.setAttribute('aria-label', label);
    b.dataset.tip = theme === 'dark' ? 'Light theme' : 'Dark theme';
  });
}

export function toggleTheme(button) {
  const next = currentTheme() === 'dark' ? 'light' : 'dark';
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!document.startViewTransition || reduce || !button) { apply(next); return; }

  const r = button.getBoundingClientRect();
  const x = r.left + r.width / 2;
  const y = r.top + r.height / 2;
  const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
  const transition = document.startViewTransition(() => apply(next));
  transition.ready.then(() => {
    document.documentElement.animate(
      { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
      { duration: 650, easing: 'cubic-bezier(0.65, 0, 0.35, 1)', pseudoElement: '::view-transition-new(root)' },
    );
  }).catch(() => { /* transition skipped: theme is already applied */ });
}

export function initThemeToggles() {
  apply(currentTheme(), false); // sync labels only; an explicit choice is saved on click
  document.querySelectorAll('.theme-toggle').forEach((b) => b.addEventListener('click', () => toggleTheme(b)));
}
