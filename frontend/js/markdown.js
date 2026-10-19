// Safe Markdown rendering: marked -> DOMPurify -> citation chips built as DOM nodes.
// Model output is never inserted as HTML without sanitising first.

const PURIFY = {
  ALLOWED_TAGS: ['p', 'br', 'strong', 'b', 'em', 'i', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'blockquote',
    'code', 'pre', 'a', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'del', 'span'],
  ALLOWED_ATTR: ['href', 'title'],
  ALLOWED_URI_REGEXP: /^(?:https?:|mailto:)/i,
};
const CITE_RE = /\[(\d{1,2})\]/g;
const HAS_CITE = /\[\d{1,2}\]/; // non-global, so .test() keeps no lastIndex state

export function renderMarkdown(el, text, { maxCite = 0 } = {}) {
  // Same normalisation as the server: 【1】 / 【1†source】 -> [1] (visible while streaming).
  const src = String(text ?? '').replace(/【\s*(\d{1,2})(?:†[^】]*)?\s*】/g, '[$1]');
  const html = window.marked.parse(src, { gfm: true, breaks: false });
  el.innerHTML = window.DOMPurify.sanitize(html, PURIFY); // sanitised above
  el.querySelectorAll('a').forEach((a) => { a.target = '_blank'; a.rel = 'noopener noreferrer'; });
  if (maxCite > 0) linkCitations(el, maxCite);
}

function linkCitations(root, maxCite) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.parentElement.closest('code, pre') || !HAS_CITE.test(n.nodeValue)
      ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const frag = document.createDocumentFragment();
    let last = 0;
    const text = node.nodeValue;
    for (const m of text.matchAll(CITE_RE)) {
      const n = Number(m[1]);
      if (n < 1 || n > maxCite) continue;
      frag.append(text.slice(last, m.index));
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'cite';
      btn.dataset.cite = String(n);
      btn.textContent = String(n);
      btn.setAttribute('aria-label', `Open source ${n}`);
      frag.append(btn);
      last = m.index + m[0].length;
    }
    frag.append(text.slice(last));
    node.replaceWith(frag);
  }
}

// Plain-text version for copying (drops citation markers).
export function plainAnswer(text) {
  return String(text ?? '').replace(CITE_RE, '').replace(/[ \t]+([.,;:])/g, '$1').trim();
}
