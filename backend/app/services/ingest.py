"""Document ingestion for the FAISS index (LangChain FAISS format, MiniLM embeddings).

Fixes the retrieval problems measured on eval/testset.json with the original index
(500-char chunks split per page, LangChain defaults):
  * "Arrangement of sections" (table of contents) pages matched title-like queries and
    crowded out the actual provisions  -> the leading TOC pages are dropped.
  * Running headers/footers and Hindi pages rendered as mojibake polluted chunks -> removed.
  * PDF extraction splits words ("sha ll")  -> conservative corpus-frequency word repair.
  * Provisions were cut at page boundaries and at arbitrary points -> chunks follow section
    headings, may span pages (page_start/page_end recorded), ~900 chars with overlap.
  * Chunks had no document context, so "... under the Indian Penal Code" barely helped
    -> each chunk's text starts with a short header: "<Document> — Section 302".

Page text is cached per file hash in data/.cache so rebuilds take seconds, not minutes.
"""
import hashlib
import json
import os
import re
from collections import Counter

from langchain_core.documents import Document

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "legal_docs")
CACHE_DIR = os.path.join(BASE_DIR, "data", ".cache")
INDEX_PATH = os.path.join(BASE_DIR, "faiss_index_v2")
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Titles from each document's first page; "Article" for the Constitution.
DOCS = {
    "ConstitutionOfIndia_pdf.pdf": ("constitution", "Constitution of India", "Article"),
    "ConsumerProtectionAct_pdf.pdf": ("consumer_protection", "Consumer Protection Act, 2019", "Section"),
    "CrPC_pdf.pdf": ("crpc", "Code of Criminal Procedure, 1973", "Section"),
    "IPC_pdf.pdf": ("ipc", "Indian Penal Code", "Section"),
    "ITAct_pdf.pdf": ("it_act", "Information Technology Act, 2000", "Section"),
    "IndianEvidenceAct_pdf.pdf": ("evidence_act", "Indian Evidence Act, 1872", "Section"),
    "LabourLaws_pdf.pdf": ("labour_laws", "Industrial, Labour and General Laws (ICSI study material)", "Section"),
    "MotorVehiclesAct_pdf.pdf": ("motor_vehicles", "Motor Vehicles Act, 1988", "Section"),
    "POCSO_pdf.pdf": ("pocso", "Protection of Children from Sexual Offences Act, 2012", "Section"),
    "faqs.txt": ("faqs", "LawTalk FAQ", "Entry"),
}
# Shown with the source so the model (and reader) can see a statute was replaced.
NOTES = {
    "ipc": "Replaced by the Bharatiya Nyaya Sanhita, 2023 (BNS) from 1 July 2024.",
    "crpc": "Replaced by the Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS) from 1 July 2024.",
    "evidence_act": "Replaced by the Bharatiya Sakshya Adhiniyam, 2023 (BSA) from 1 July 2024.",
}

CHUNK_SIZE = 900
CHUNK_OVERLAP = 150

HEADER_RE = re.compile(  # "302. Punishment for murder.—Whoever"
    # a-z in the lookbehind: the Constitution PDF glues sub-headings on ("Right to Equality14.")
    r"(?:^|(?<=[\n\]\.;:\)a-z]))[ \t]*(?:\d{1,2}\[)?(\d{1,3}[A-Z]{0,3})\.\s*"
    r"([A-Z](?:[^\n—–]|\n(?!\s*\d{1,3}[A-Z]{0,3}\.)){2,200}?)\s*\.?\s*[—–]+",
    re.M,
)
_TOC_ENTRY_RE = re.compile(r"(?:^|[\s\]\.])\d{1,3}[A-Z]{0,3}\.\s?[A-Z][a-z]")
_WORD_RE = re.compile(r"[A-Za-z]+")
_MOJIBAKE_RE = re.compile(r"[À-ÿ¡-¿]")
_CONST_HEADER_RE = re.compile(r"^\s*THE CONSTITUTION OF INDIA\s*(?:\([^)]{0,80}\))?\s*\d{0,3}")


# --------------------------------------------------------------------------- text
def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:16]


def _clean(text: str) -> str:
    text = text.replace("�", "—").replace("­", "")
    text = re.sub(r"[ \t ]+", " ", text)
    return re.sub(r" *\n *", "\n", text).strip()


def extract_pages(path: str) -> list[str]:
    """Cleaned text per page (index 0 = physical page 1), cached by file hash."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    name = os.path.basename(path)
    cache = os.path.join(CACHE_DIR, f"{name}-{_sha(path)}.json")
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    if name.lower().endswith(".pdf"):
        from pypdf import PdfReader

        pages = [_clean(p.extract_text() or "") for p in PdfReader(path).pages]
    else:
        with open(path, encoding="utf-8") as f:
            pages = [_clean(f.read())]
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False)
    return pages


def strip_boilerplate(pages: list[str], doc_id: str) -> list[str]:
    """Remove lines repeated on >=30% of pages (running headers/footers) and page numbers."""
    norm = lambda s: re.sub(r"\d+", "#", s.strip().lower())  # noqa: E731
    counts: Counter = Counter()
    if len(pages) >= 10:
        for p in pages:
            counts.update({norm(ln) for ln in p.split("\n") if 0 < len(ln.strip()) < 120})
    threshold = max(3, int(0.3 * len(pages)))
    out = []
    for p in pages:
        lines = [ln for ln in p.split("\n") if len(pages) < 10 or counts[norm(ln)] < threshold]
        while lines and re.fullmatch(r"\s*\d{1,4}\s*", lines[0]):
            lines.pop(0)
        text = "\n".join(lines)
        if doc_id == "constitution":
            text = _CONST_HEADER_RE.sub("", text, count=1)
        out.append(text.strip())
    return out


def repair_split_words(text: str, vocab: Counter) -> str:
    """Re-join PDF-split words ("sha ll" -> "shall") only when the joined word is common in
    the corpus and more frequent than both fragments, so real word pairs stay apart."""

    def merge(m: re.Match) -> str:
        a, b = m.group(1), m.group(2)
        f = vocab.get((a + b).lower(), 0)
        return a if f >= 3 and f > vocab.get(a.lower(), 0) and f > vocab.get(b.lower(), 0) else m.group(0)

    pattern = re.compile(r"\b([A-Za-z]{1,12}) (?=([a-z]{1,12})\b)")
    for _ in range(2):
        text = pattern.sub(merge, text)
    return text


def _is_toc(text: str) -> bool:
    entries = len(_TOC_ENTRY_RE.findall(text))
    bodies = text.count(".—") + text.count(". —") + text.count(".–")
    return entries >= 6 and bodies <= max(1, entries // 8)


def leading_toc_pages(pages: list[str]) -> set[int]:
    """1-based pages of the arrangement-of-sections block at the start of a document."""
    toc: set[int] = set()
    misses = 0
    for i, p in enumerate(pages):
        if _is_toc(p):
            toc.add(i + 1)
            misses = 0
        elif toc or i >= 4:
            misses += 1
            if misses >= 2 or not toc:
                break
    return toc


# --------------------------------------------------------------------------- sections
# Section/article labels are only detected in statutes. The labour-law study material uses
# lesson numbering and the FAQ has none, so labels there would be misleading.
STATUTES = {"constitution", "consumer_protection", "crpc", "ipc", "it_act", "evidence_act", "motor_vehicles", "pocso"}
# "35. (1) A complaint ..." - sections without an inline title (e.g. Consumer Protection Act).
UNTITLED_RE = re.compile(r"(?:^|(?<=[\n\]]))[ \t]*(\d{1,3}[A-Z]{0,3})\.\s*\((?:1|i)\)\s+[A-Z]", re.M)


# Amendment footnotes ("4. Ins. by ...", "2. Subs. by ...") look like headings.
_FOOTNOTE_RE = re.compile(r"(Subs|Ins|Omitted|Added|Rep|Renumbered|Inserted|Substituted|The words|Cl\.|Sub-s|See)\b", re.I)


def _num(label: str) -> int:
    return int(re.match(r"\d+", label).group())


def detect_headers(doc_text: str) -> list[tuple[int, str, str | None]]:
    """(offset, number, title) for each provision heading, in document order.

    The real provisions form one long non-decreasing run of numbers. Appendices of amending
    Acts ("38. Amendment of section 438"), the Constitution's Schedules (whose paragraph
    numbers repeat article numbers) and stray cross-references form short separate runs,
    so only the longest non-decreasing subsequence is kept; text in the dropped parts is
    attributed to no provision rather than to a wrong one. Titles longer than a heading
    normally is (a sentence caught by the pattern) are rejected.
    """
    from bisect import bisect_right

    found = []
    # Overlapping search: a footnote such as "4. Ins. by ... Act, 1976 ..." can match and
    # run on to the next heading's dash; resuming right after each number keeps the real
    # heading inside it as a candidate. Footnote-like titles are then rejected.
    pos = 0
    while (m := HEADER_RE.search(doc_text, pos)) is not None:
        pos = m.start(1) + 1
        title = re.sub(r"\s+", " ", m.group(2)).strip(" .")
        if len(title) <= 140 and len(title.split()) <= 24 and not _FOOTNOTE_RE.match(title):
            found.append((m.start(1), m.group(1), title))
    for m in UNTITLED_RE.finditer(doc_text):
        found.append((m.start(1), m.group(1), None))
    found.sort()
    nums = [_num(n) for _, n, _ in found]
    # Longest non-decreasing subsequence (patience sorting with back-pointers).
    tails, tail_idx, prev = [], [], [-1] * len(nums)
    for i, n in enumerate(nums):
        pos = bisect_right(tails, n)
        if pos == len(tails):
            tails.append(n)
            tail_idx.append(i)
        else:
            tails[pos], tail_idx[pos] = n, i
        prev[i] = tail_idx[pos - 1] if pos else -1
    keep, i = [], tail_idx[-1] if tail_idx else -1
    while i >= 0:
        keep.append(i)
        i = prev[i]
    out = []
    for i in reversed(keep):
        off, num, title = found[i]
        if out and out[-1][1] == num:  # same provision matched by both patterns
            if title and not out[-1][2]:
                out[-1] = (out[-1][0], num, title)
            continue
        out.append((off, num, title))
    return out


# --------------------------------------------------------------------------- chunks
def _splitter():
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            r"\n\n(?=\d{1,3}[A-Z]{0,3}\.\s*[A-Z])",
            r"\n(?=\d{1,3}[A-Z]{0,3}\.\s*[A-Z])",
            r"(?<=[\.\]])(?=(?:\d{1,2}\[)?\d{1,3}[A-Z]{0,3}\.\s?[A-Z][a-z])",
            r"\n\n", r"\n", r"(?<=[\.;:])\s", r" ", r"",
        ],
        is_separator_regex=True,
        keep_separator="start",
        add_start_index=True,
    )


def chunk_document(file: str, pages: list[str], vocab: Counter, context_header: bool = True) -> list[Document]:
    doc_id, title, unit = DOCS.get(file, (os.path.splitext(file)[0].lower(), os.path.splitext(file)[0], "Section"))
    pages = [repair_split_words(p, vocab) for p in strip_boilerplate(pages, doc_id)]
    offsets, pos = [], 0
    for p in pages:
        offsets.append(pos)
        pos += len(p) + 2
    doc_text = "\n\n".join(pages)

    def page_at(off: int) -> int:
        lo, hi = 0, len(offsets) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            lo, hi = (mid, hi) if offsets[mid] <= off else (lo, mid - 1)
        return lo + 1

    toc = leading_toc_pages(pages)
    headers = detect_headers(doc_text) if doc_id in STATUTES else []
    out, seen = [], set()
    for d in _splitter().create_documents([doc_text]):
        text = d.page_content.strip()
        start = d.metadata["start_index"]
        if len(text) < 50 or text.replace(" ", "").isdigit() or ("EP-IL&GL" in text and len(text) < 120):
            continue
        if _MOJIBAKE_RE.findall(text) and len(_MOJIBAKE_RE.findall(text)) / len(text) > 0.15:
            continue
        key = re.sub(r"\W+", "", text.lower())
        if key in seen:
            continue
        seen.add(key)
        p_start, p_end = page_at(start), page_at(start + len(text) - 1)
        if p_start in toc and p_end in toc:
            continue
        in_force, inside = None, []
        for off, num, ttl in headers:
            if off < start:
                in_force = (num, ttl)
            elif off < start + len(text):
                inside.append((num, ttl))
            else:
                break
        first = HEADER_RE.search(text)
        touched = ([in_force] if in_force and (not inside or first is None or first.start(1) > 40) else []) + inside
        primary = inside[0] if inside else in_force
        sections = list(dict.fromkeys(n for n, _ in touched))
        label = (f"{unit} {primary[0]}" + (f" ({primary[1][:90]})" if primary[1] else "")) if primary else None
        header = title + (f" — {label}" if label else "")
        content = f"{header}\n{text}" if context_header else text
        out.append(Document(
            page_content=content,
            metadata={
                "source": file, "doc_id": doc_id, "title": title,
                "page": p_start - 1, "page_end": p_end - 1,  # 0-based, like PyPDFLoader's "page"
                "section": primary[0] if primary else None,
                "section_title": primary[1][:120] if primary and primary[1] else None,
                "section_kind": unit if primary else None,
                "sections": sections,
                "note": NOTES.get(doc_id),
                "chunk_id": f"{doc_id}-{p_start:04d}-{start:07d}",
            },
        ))
    return out


def build_documents(context_header: bool = True) -> list[Document]:
    files = sorted(f for f in os.listdir(DATA_PATH) if f.endswith((".pdf", ".txt")))
    pages = {f: extract_pages(os.path.join(DATA_PATH, f)) for f in files}
    vocab = Counter(w.lower() for ps in pages.values() for p in ps for w in _WORD_RE.findall(p))
    docs: list[Document] = []
    for f in files:
        docs.extend(chunk_document(f, pages[f], vocab, context_header))
    return docs


def build_index(out_dir: str = INDEX_PATH, context_header: bool = True):
    from langchain_community.vectorstores import FAISS
    from langchain_huggingface import HuggingFaceEmbeddings

    docs = build_documents(context_header)
    emb = HuggingFaceEmbeddings(model_name=EMBED_MODEL, encode_kwargs={"normalize_embeddings": True})
    db = FAISS.from_documents(docs, emb, ids=[d.metadata["chunk_id"] for d in docs])
    db.save_local(out_dir)
    print(f"Built {out_dir}: {len(docs)} chunks")
    return db


if __name__ == "__main__":
    import sys

    if "--extract-only" in sys.argv:
        for f in sorted(os.listdir(DATA_PATH)):
            if f.endswith((".pdf", ".txt")):
                print(f, len(extract_pages(os.path.join(DATA_PATH, f))), "pages", flush=True)
    else:
        build_index(sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else INDEX_PATH,
                    context_header="--no-header" not in sys.argv)
