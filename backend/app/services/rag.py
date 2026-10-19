import os
import re
import threading
import time
from functools import lru_cache

import numpy as np
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import BASE_DIR, TOP_K

DB_PATH = os.path.join(BASE_DIR, "faiss_index")
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Display titles for the bundled documents (taken from each document's first page).
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

db = None
_encode_lock = threading.Lock()


def load_db():
    """Load the embedding model and FAISS index once (called at app startup)."""
    global db
    if db is None:
        embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
        # The index is produced by our own ingestion script (app/services/embedder.py).
        db = FAISS.load_local(DB_PATH, embeddings, allow_dangerous_deserialization=True)
        _embed("warm up")
    return db


def _normalize(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


@lru_cache(maxsize=1024)
def _embed(norm_query: str) -> np.ndarray:
    with _encode_lock:  # one encode at a time; a query encode takes ~15 ms
        vec = db.embedding_function.embed_query(norm_query)
    return np.asarray([vec], dtype="float32")


@lru_cache(maxsize=1024)
def _search(norm_query: str, k: int) -> tuple:
    distances, ids = db.index.search(_embed(norm_query), k)
    return tuple((int(i), float(d)) for i, d in zip(ids[0], distances[0]) if i >= 0)


def _source(n: int, idx: int, distance: float) -> dict:
    chunk_id = db.index_to_docstore_id[idx]
    doc = db.docstore.search(chunk_id)
    meta = doc.metadata or {}
    file = os.path.basename(meta.get("source", "").replace("\\", "/")) or None
    page = meta.get("page")
    return {
        "id": n,
        "chunk_id": chunk_id,
        "title": TITLES.get(file, file) if file else None,
        "file": file,
        # 1-based PDF page; only present when the loader recorded one.
        "page": page + 1 if isinstance(page, int) else None,
        "text": doc.page_content,
        # Vectors are unit length, so cosine similarity = 1 - squared_L2 / 2.
        "score": round(1 - distance / 2, 4),
    }


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
