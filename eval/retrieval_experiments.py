"""Retrieval experiments on eval/testset.json (no LLM calls).

Each variant runs in a fresh process with its own settings, and labels are resolved for
that variant's index with the same rule as build_testset.py, so indexes with different
chunking are compared on the same questions and the same evidence.

    python eval/retrieval_experiments.py            # writes eval/retrieval_experiments.json
"""
import json
import os
import subprocess
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
ROOT = EVAL_DIR.parent
BACKEND = ROOT / "backend"

VARIANTS = [
    ("original index, dense", "faiss_index", {"RETRIEVAL_HYBRID": "0", "RETRIEVAL_SECTION_LOOKUP": "0"}),
    ("original index, dense + BM25", "faiss_index", {"RETRIEVAL_HYBRID": "1", "RETRIEVAL_SECTION_LOOKUP": "0"}),
    ("new chunks (no header), dense", "faiss_index_v2_noheader", {"RETRIEVAL_HYBRID": "0", "RETRIEVAL_SECTION_LOOKUP": "0"}),
    ("new chunks + context header, dense", "faiss_index_v2", {"RETRIEVAL_HYBRID": "0", "RETRIEVAL_SECTION_LOOKUP": "0"}),
    ("new chunks + header, dense + BM25", "faiss_index_v2", {"RETRIEVAL_HYBRID": "1", "RETRIEVAL_SECTION_LOOKUP": "0"}),
    ("new chunks + header, dense + BM25 + section lookup", "faiss_index_v2", {"RETRIEVAL_HYBRID": "1", "RETRIEVAL_SECTION_LOOKUP": "1"}),
    ("... + cross-encoder rerank", "faiss_index_v2", {"RETRIEVAL_HYBRID": "1", "RETRIEVAL_SECTION_LOOKUP": "1", "RETRIEVAL_RERANK": "1"}),
]

WORKER = r'''
import json, sys, time, statistics
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
from build_testset import SEEDS, load_chunks, resolve
from pathlib import Path
from app.services import rag
rag.load_db()
chunks = load_chunks(Path(rag.DB_PATH))
rows, times = [], []
for tid, question, _ref, evidence in SEEDS:
    if not evidence:
        continue
    rel = set(resolve(chunks, tid, evidence))
    t = time.perf_counter()
    top = [s["chunk_id"] for s in rag.retrieve(question, k=5)]
    times.append((time.perf_counter() - t) * 1000)
    rag._search.cache_clear(); rag._embed.cache_clear()
    ranks = [r + 1 for r, c in enumerate(top) if c in rel]
    rows.append({"id": tid, "recall": len(rel & set(top)) / len(rel), "hit": float(bool(ranks)),
                 "mrr": 1 / ranks[0] if ranks else 0.0, "n_relevant": len(rel)})
mean = lambda k: round(sum(r[k] for r in rows) / len(rows), 3)
print(json.dumps({"chunks": rag.db.index.ntotal, "recall@5": mean("recall"), "hit@5": mean("hit"), "mrr@5": mean("mrr"),
                  "avg_relevant_chunks": round(sum(r["n_relevant"] for r in rows) / len(rows), 2),
                  "retrieve_ms_p50": round(statistics.median(times), 1), "misses": [r["id"] for r in rows if not r["hit"]],
                  "per_item": rows}))
'''


def main() -> None:
    results = []
    for name, index, env in VARIANTS:
        if not (BACKEND / index / "index.faiss").exists():
            print(f"skip {name}: {index} not built")
            continue
        e = {**os.environ, "FAISS_INDEX_DIR": str(BACKEND / index), "RETRIEVAL_RERANK": "0", **env,
             "PYTHONIOENCODING": "utf-8"}
        out = subprocess.run([sys.executable, "-c", WORKER, str(BACKEND), str(EVAL_DIR)], cwd=BACKEND, env=e,
                             capture_output=True, text=True, encoding="utf-8")
        line = [l for l in out.stdout.splitlines() if l.startswith("{")]
        if not line:
            print(f"{name}: FAILED\n{out.stderr[-1500:]}")
            continue
        r = {"variant": name, "index": index, "settings": env, **json.loads(line[-1])}
        results.append(r)
        print(f"{name:<55} recall@5={r['recall@5']:.3f} hit@5={r['hit@5']:.3f} mrr={r['mrr@5']:.3f} "
              f"chunks={r['chunks']} retrieve_p50={r['retrieve_ms_p50']}ms misses={r['misses']}", flush=True)
    (EVAL_DIR / "retrieval_experiments.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
