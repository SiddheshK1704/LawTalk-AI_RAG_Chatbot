"""Retrieval: FAISS dense search (MiniLM) + BM25 lexical search, fused, with exact
section/article lookup. Loaded once at startup; repeated queries hit LRU caches.

Each stage can be switched off via environment variables so its effect can be measured
(eval/retrieval_experiments.py): RETRIEVAL_HYBRID, RETRIEVAL_SECTION_LOOKUP, RETRIEVAL_RERANK.
"""
import os
import re
import threading
import time
from collections import Counter
from functools import lru_cache

import numpy as np
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import BASE_DIR, TOP_K

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_V2 = os.path.join(BASE_DIR, "faiss_index_v2")
_V1 = os.path.join(BASE_DIR, "faiss_index")
# Prefer the rebuilt index (app/services/ingest.py); fall back to the original one.
DB_PATH = os.getenv("FAISS_INDEX_DIR") or (_V2 if os.path.exists(os.path.join(_V2, "index.faiss")) else _V1)

HYBRID = os.getenv("RETRIEVAL_HYBRID", "1") == "1"
SECTION_LOOKUP = os.getenv("RETRIEVAL_SECTION_LOOKUP", "1") == "1"
RERANK = os.getenv("RETRIEVAL_RERANK", "0") == "1"
CANDIDATES = 30

# Display titles for chunks from the original index (v2 chunks carry their own title).
TITLES = {
    "ConstitutionOfIndia_pdf.pdf": "Constitution of India",
    "ConsumerProtectionAct_pdf.pdf": "Consumer Protection Act, 2019",
    "CrPC_pdf.pdf": "Code of Criminal Procedure, 1973",
    "IPC_pdf.pdf": "Indian Penal Code",
    "ITAct_pdf.pdf": "Information Technology Act, 2000",
    "IndianEvidenceAct_pdf.pdf": "Indian Evidence Act, 1872",
    "LabourLaws_pdf.pdf": "Industrial, Labour and General Laws (ICSI study material)",
    "MotorVehiclesAct_pdf.pdf": "Motor Vehicles Act, 1988",
    "POCSO_pdf.pdf": "Protection of Children from Sexual Offences Act, 2012",
    "faqs.txt": "LawTalk FAQ",
}
# Phrases users write when naming an Act -> doc_id used in v2 metadata.
DOC_ALIASES = {
    "ipc": r"\bi\.?p\.?c\b|indian penal code|penal code",
    "crpc": r"\bcr\.?\s?p\.?c\b|code of criminal procedure|criminal procedure code",
    "evidence_act": r"evidence act",
    "it_act": r"\bit act\b|information technology act",
    "motor_vehicles": r"motor vehicles? act|\bmv act\b",
    "pocso": r"\bpocso\b",
    "consumer_protection": r"consumer protection act",
}
_ALIAS_RE = {d: re.compile(p, re.I) for d, p in DOC_ALIASES.items()}
_SECTION_RE = re.compile(r"\b(?:section|sec\.?|s\.)\s*(\d{1,3}[a-z]{0,3})\b", re.I)
_ARTICLE_RE = re.compile(r"\b(?:article|art\.)\s*(\d{1,3}[a-z]{0,2})\b", re.I)
_BARE_RE = re.compile(r"\b(ipc|crpc)\s*(\d{1,3}[a-z]{0,2})\b|\b(\d{1,3}[a-z]{0,2})\s*(?:of\s+)?(?:the\s+)?(ipc|crpc)\b", re.I)
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Everyday legal terms that the statutes themselves never use, mapped to the statutory
# wording. Appended to the query so both dense and lexical search can match the text.
GLOSSARY = {
    "anticipatory bail": "bail to person apprehending arrest",
    "fir": "information in cognizable cases",
    "first information report": "information in cognizable cases",
    "dying declaration": "statement made by a person as to the cause of his death",
    "chargesheet": "report of police officer on completion of investigation",
    "charge sheet": "report of police officer on completion of investigation",
    "remand": "detention in custody pending investigation",
    "drunk driving": "driving by a drunken person",
    "drink and drive": "driving by a drunken person",
    "hit and run": "hit and run motor accident compensation",
    "cybercrime": "computer related offences",
    "cyber crime": "computer related offences",
    "identity theft": "identity theft password unique identification feature",
    "custodial death": "death in police custody",
}
_GLOSSARY_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in GLOSSARY) + r")\b")
# "Who is a child under ...", "what is a consumer", "meaning of ...", "define ..."
_DEFINE_RE = re.compile(
    r"\b(?:who|what)\s+(?:is|are)\s+(?:an?\s+|the\s+)?([a-z][a-z\-]*(?:\s[a-z][a-z\-]*){0,2}?)"
    r"(?=\s+(?:under|in|according|as\s+per|for)\b|\s*\?|$)"
    r"|\b(?:meaning|definition)\s+of\s+(?:an?\s+|the\s+)?([a-z][a-z\-]*(?:\s[a-z][a-z\-]*){0,2})"
    r"|\bdefine\s+(?:an?\s+|the\s+)?([a-z][a-z\-]*(?:\s[a-z][a-z\-]*){0,2})"
)


def _stem(w: str) -> str:
    """Tiny suffix stripper so "file"/"filed"/"files" and "complaint"/"complaints" match."""
    for suf in ("ing", "ed", "es", "s", "e"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def expand_query(norm_query: str) -> str:
    extra = [GLOSSARY[m.group(1)] for m in _GLOSSARY_RE.finditer(norm_query)]
    return norm_query + (" (" + "; ".join(dict.fromkeys(extra)) + ")" if extra else "")
_STOP = set("the a an of to in on for and or is are be by with what which who whom when where how can does do under any "
            "from as at this that it its into than there their about my me i you your shall may".split())

db = None
_encode_lock = threading.Lock()
_bm25 = None
_by_section: dict[tuple[str, str], list[int]] = {}
_definitions: dict[str, list[int]] = {}
_DEF_CLAUSE_RE = re.compile(r'"([A-Za-z][A-Za-z \-]{1,40})"\s+means\b')
_reranker = None


class _BM25:
    """Okapi BM25 over chunk texts (sparse matrix; ~1 s to build for ~7k chunks)."""

    def __init__(self, texts: list[str], k1: float = 1.4, b: float = 0.7):
        from scipy.sparse import csr_matrix

        docs = [[_stem(w) for w in _TOKEN_RE.findall(t.lower()) if w not in _STOP] for t in texts]
        self.vocab: dict[str, int] = {}
        rows, cols, vals = [], [], []
        for i, d in enumerate(docs):
            for w, c in Counter(d).items():
                rows.append(i)
                cols.append(self.vocab.setdefault(w, len(self.vocab)))
                vals.append(c)
        tf = csr_matrix((vals, (rows, cols)), shape=(len(docs), len(self.vocab)), dtype=np.float32)
        dl = np.array([len(d) for d in docs], dtype=np.float32)
        df = np.bincount(tf.indices, minlength=len(self.vocab))
        self.idf = np.log(1 + (len(docs) - df + 0.5) / (df + 0.5)).astype(np.float32)
        denom = k1 * (1 - b + b * dl / max(1.0, dl.mean()))
        tf.data = tf.data * (k1 + 1) / (tf.data + np.repeat(denom, np.diff(tf.indptr)))
        self.matrix = tf.tocsc()

    def search(self, query: str, k: int) -> list[int]:
        toks = {_stem(w) for w in _TOKEN_RE.findall(query) if w not in _STOP}
        ids = [self.vocab[w] for w in toks if w in self.vocab]
        if not ids:
            return []
        scores = np.asarray(self.matrix[:, ids].multiply(self.idf[ids]).sum(axis=1)).ravel()
        k = min(k, len(scores))
        top = np.argpartition(-scores, k - 1)[:k]
        return [int(i) for i in top[np.argsort(-scores[top])] if scores[i] > 0]


def load_db():
    """Load the embedding model, FAISS index, BM25 and section map once (app startup)."""
    global db, _bm25, _reranker
    if db is None:
        embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL, encode_kwargs={"normalize_embeddings": True})
        # The index is produced by our own ingestion script (app/services/ingest.py).
        db = FAISS.load_local(DB_PATH, embeddings, allow_dangerous_deserialization=True)
        n = db.index.ntotal
        docs = [db.docstore.search(db.index_to_docstore_id[i]) for i in range(n)]
        if HYBRID:
            # The first line of a v2 chunk is its header (document + provision title); it is
            # counted twice so titles like "Order for maintenance of wives, children and
            # parents" outweigh passing mentions elsewhere.
            _bm25 = _BM25([d.page_content.split("\n", 1)[0] + "\n" + d.page_content if (d.metadata or {}).get("chunk_id")
                           else d.page_content for d in docs])
        for i, d in enumerate(docs):
            m = d.metadata or {}
            for s in m.get("sections") or []:
                _by_section.setdefault((m.get("doc_id"), s.upper()), []).append(i)
            # Definition clauses: '"child" means ...' (curly or straight quotes).
            for term in _DEF_CLAUSE_RE.findall(d.page_content.replace("\u201c", '"').replace("\u201d", '"')):
                _definitions.setdefault(" ".join(term.lower().split()), []).append(i)
        if RERANK:
            from sentence_transformers import CrossEncoder

            _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
        _embed("warm up")
    return db


def _normalize(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


@lru_cache(maxsize=1024)
def _embed(norm_query: str) -> np.ndarray:
    with _encode_lock:  # one encode at a time; a query encode takes ~15 ms
        vec = db.embedding_function.embed_query(norm_query)
    return np.asarray([vec], dtype="float32")


def section_refs(query: str) -> list[tuple[str, str]]:
    """Explicit references such as 'Article 21', 'Section 438 CrPC', 'IPC 420'."""
    refs = [("constitution", m.group(1).upper()) for m in _ARTICLE_RE.finditer(query)]
    for m in _BARE_RE.finditer(query):
        refs.append(((m.group(1) or m.group(4)).lower(), (m.group(2) or m.group(3)).upper()))
    secs = [m.group(1).upper() for m in _SECTION_RE.finditer(query)]
    named = [d for d, rx in _ALIAS_RE.items() if rx.search(query)]
    if secs and len(named) == 1:  # section numbers repeat across Acts: only resolve when one Act is named
        refs += [(named[0], s) for s in secs]
    return list(dict.fromkeys(refs))


def definition_hits(norm_query: str) -> list[int]:
    """Chunks containing the statutory definition asked about ("who is a child under POCSO")."""
    m = _DEFINE_RE.search(norm_query)
    if not m:
        return []
    term = " ".join((m.group(1) or m.group(2) or m.group(3) or "").split())
    hits = _definitions.get(term) or _definitions.get(term.rstrip("s")) or []
    named = [d for d, rx in _ALIAS_RE.items() if rx.search(norm_query)]
    if named:  # prefer the Act the user named
        hits = [i for i in hits if (db.docstore.search(db.index_to_docstore_id[i]).metadata or {}).get("doc_id") in named] or hits
    return hits[:1]


@lru_cache(maxsize=1024)
def _search(norm_query: str, k: int) -> tuple:
    norm_query = expand_query(norm_query)
    vec = _embed(norm_query)
    distances, ids = db.index.search(vec, CANDIDATES)
    dense = [(int(i), float(d)) for i, d in zip(ids[0], distances[0]) if i >= 0]
    dist = dict(dense)
    order = [i for i, _ in dense]
    if _bm25 is not None:  # reciprocal-rank fusion of dense and lexical rankings
        fused: dict[int, float] = {}
        for ranking in (order, _bm25.search(norm_query, CANDIDATES)):
            for rank, i in enumerate(ranking):
                fused[i] = fused.get(i, 0.0) + 1.0 / (60 + rank + 1)
        order = sorted(fused, key=fused.get, reverse=True)
    if _reranker is not None:
        pool = order[:CANDIDATES]
        texts = [db.docstore.search(db.index_to_docstore_id[i]).page_content for i in pool]
        scores = _reranker.predict([(norm_query, t) for t in texts])
        order = [i for _, i in sorted(zip(scores, pool), key=lambda z: -z[0])]
    pinned = []
    if SECTION_LOOKUP:
        for ref in section_refs(norm_query):
            # First occurrence in document order is the main provision (later repeats are
            # Schedule paragraphs); take its heading chunk and the one after it.
            pinned += sorted(_by_section.get(ref, []))[:2]
        pinned += definition_hits(norm_query)
    final = list(dict.fromkeys(pinned + order))[:k]
    out = []
    for i in final:
        if i not in dist:  # cosine distance for chunks found only lexically / by lookup
            v = db.index.reconstruct(i)
            dist[i] = float(np.sum((vec[0] - v) ** 2))
        out.append((i, dist[i]))
    return tuple(out)


def _source(n: int, idx: int, distance: float) -> dict:
    chunk_id = db.index_to_docstore_id[idx]
    doc = db.docstore.search(chunk_id)
    meta = doc.metadata or {}
    file = os.path.basename(meta.get("source", "").replace("\\", "/")) or None
    page = meta.get("page")
    page_end = meta.get("page_end", page)
    return {
        "id": n,
        "chunk_id": chunk_id,
        "title": meta.get("title") or (TITLES.get(file, file) if file else None),
        "file": file,
        # 1-based PDF pages; only present when the loader recorded them.
        "page": page + 1 if isinstance(page, int) else None,
        "page_end": page_end + 1 if isinstance(page_end, int) and page_end != page else None,
        # Section heading detected in the document text (v2 index only).
        "section": meta.get("section"),
        "section_title": meta.get("section_title"),
        "section_kind": meta.get("section_kind"),
        "note": meta.get("note"),
        "text": doc.page_content,
        # Vectors are unit length, so cosine similarity = 1 - squared_L2 / 2.
        "score": round(1 - distance / 2, 4),
    }


def max_similarity(query: str) -> float:
    """Best dense cosine similarity for the query (used by the mode router)."""
    distances, _ = db.index.search(_embed(_normalize(query)), 1)
    return float(1 - distances[0][0] / 2)


def retrieve(query: str, timer=None, k: int = TOP_K) -> list[dict]:
    """Top-k chunks with metadata. Repeated questions hit the embedding/search caches."""
    norm = _normalize(query)
    t = time.perf_counter()
    _embed(norm)
    t_embed = time.perf_counter()
    hits = _search(norm, k)
    sources = [_source(n, idx, d) for n, (idx, d) in enumerate(hits, start=1)]
    if timer is not None:
        timer.add("embed", t_embed - t)
        timer.add("retrieve", time.perf_counter() - t_embed)
    return sources
