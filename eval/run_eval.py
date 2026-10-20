"""LawTalk evaluation. Start the backend first (uvicorn on :8000), then from the repo root:

    python eval/run_eval.py                    # everything
    python eval/run_eval.py --skip-benchmark   # quality metrics only
    python eval/run_eval.py --skip-ragas       # retrieval + latency only

Measures
  * RAGAS (v0.4 collections API): Faithfulness, Answer Relevancy, Context Precision
    (with reference), Context Recall, on the answerable questions of eval/testset.json
  * Retrieval Recall@5 against the labelled relevant chunk IDs (no LLM)
  * Citation correctness: an LLM judge checks each cited passage supports its sentence (~10 answers)
  * p95 latency and error rate: eval/benchmark.py, 50 requests (30 sequential + 20 concurrent)

Answers come from the running server (POST /ask/stream), i.e. the real pipeline.
The judge model is separate from the answer model (default qwen/qwen3.8-27b on Groq, which has
its own rate-limit and daily-token budget, so judging does not compete with the answer model).
Results: eval/results.json and eval/results.md. If eval/baseline.json exists (created by
`python eval/benchmark.py --base-url <original server> --label baseline`), a before/after
latency comparison is printed and saved.
"""
import argparse
import asyncio
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import httpx

EVAL_DIR = Path(__file__).resolve().parent
ROOT = EVAL_DIR.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(EVAL_DIR))
os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
# The live app fails fast after 20 s of waiting for tokens-per-minute budget; an evaluation
# should wait instead, otherwise it measures that policy rather than the pipeline.
os.environ.setdefault("GROQ_MAX_QUEUE_S", "120")

from benchmark import auth_headers, run_benchmark  # noqa: E402

GROQ_BASE = "https://api.groq.com/openai/v1"


def mean(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    return round(sum(xs) / len(xs), 3) if xs else None


# ---------------------------------------------------------------------------
# 1. Retrieval Recall@5 (in-process, same retrieval code as the server)
# ---------------------------------------------------------------------------
def retrieval_recall(items: list[dict], k: int = 5) -> dict:
    from app.services import rag

    rag.load_db()
    rows = []
    for it in items:
        if not it["answerable"]:
            continue
        top = [s["chunk_id"] for s in rag.retrieve(it["question"], k=k)]
        legacy = os.path.basename(rag.DB_PATH) == "faiss_index"
        rel = set(it["relevant_chunk_ids_legacy"] if legacy and "relevant_chunk_ids_legacy" in it else it["relevant_chunk_ids"])
        found = rel & set(top)
        rows.append({"id": it["id"], "recall": len(found) / len(rel), "hit": float(bool(found))})
    return {"recall_at_5": mean([r["recall"] for r in rows]), "hit_rate_at_5": mean([r["hit"] for r in rows]),
            "n": len(rows), "per_item": rows}


# ---------------------------------------------------------------------------
# 2. Answers from the real pipeline
# ---------------------------------------------------------------------------
async def generate_answers(base_url: str, items: list[dict], delay: float) -> list[dict]:
    out = []
    async with httpx.AsyncClient(timeout=120, headers=auth_headers()) as client:
        for it in items:
            t0 = time.perf_counter()
            rec = {"id": it["id"], "ok": False}
            try:
                async with client.stream("POST", base_url + "/ask/stream", json={"query": it["question"]}) as r:
                    event = None
                    async for line in r.aiter_lines():
                        if line.startswith("event:"):
                            event = line[6:].strip()
                        elif line.startswith("data:"):
                            data = json.loads(line[5:])
                            if event == "sources":
                                rec["mode"] = data.get("mode")
                            elif event == "token" and "ttft_s" not in rec:
                                rec["ttft_s"] = time.perf_counter() - t0
                            elif event == "done":
                                rec.update(ok=True, answer=data["answer"], citations=data["citations"],
                                           sources=data["sources"], mode=data.get("mode", rec.get("mode")))
                            elif event == "error":
                                rec["error"] = data.get("code")
            except httpx.HTTPError as e:
                rec["error"] = type(e).__name__
            rec["e2e_s"] = time.perf_counter() - t0
            print(f"  answer {it['id']}: {'ok' if rec['ok'] else rec.get('error')} ({rec['e2e_s']:.1f}s)", flush=True)
            out.append(rec)
            await asyncio.sleep(delay)
    return out


async def generate_answers_inprocess(items: list[dict], delay: float) -> list[dict]:
    """Same pipeline as /ask/stream (router -> retrieval -> prompt -> streamed Groq call),
    called directly instead of over HTTP. Used when no EVAL_AUTH_TOKEN is available."""
    from app.api.chat import finalize, plan
    from app.core.metrics import RequestTimer
    from app.services.groq_client import LLMError, stream_llm_response

    out = []
    for it in items:
        t0 = time.perf_counter()
        rec = {"id": it["id"], "ok": False}
        timer = RequestTimer()
        try:
            mode, sources, messages = plan(it["question"], timer)
            rec["mode"] = mode
            parts = []
            async for delta in stream_llm_response(messages, timer):
                if "ttft_s" not in rec:
                    rec["ttft_s"] = time.perf_counter() - t0
                parts.append(delta)
            answer, cited = finalize("".join(parts), sources)
            rec.update(ok=True, answer=answer, citations=cited, sources=sources)
        except LLMError as e:
            rec["error"] = e.code
        rec["e2e_s"] = time.perf_counter() - t0
        rec["stages"] = {k: round(v, 3) for k, v in timer.stages.items()}
        print(f"  answer {it['id']}: {'ok' if rec['ok'] else rec.get('error')} mode={rec.get('mode')} ({rec['e2e_s']:.1f}s)", flush=True)
        out.append(rec)
        await asyncio.sleep(delay)
    return out


async def benchmark_inprocess(questions: list[str], sequential: int = 30, concurrent: int = 20,
                              concurrency: int = 4, delay: float = 2.0, warmup: int = 2) -> dict:
    """The eval/benchmark.py protocol (30 sequential + 20 concurrent, like /ask) run against
    the pipeline in-process: it excludes HTTP and the (cached) auth check."""
    from app.api.chat import finalize, plan
    from app.core.metrics import RequestTimer
    from app.services.groq_client import LLMError, get_llm_response
    from benchmark import summarize_records

    async def one(q: str) -> dict:
        t0 = time.perf_counter()
        rec = {"ok": False}
        try:
            _mode, sources, messages = await asyncio.to_thread(plan, q, RequestTimer())
            finalize(await get_llm_response(messages, RequestTimer()), sources)
            rec["ok"] = True
        except LLMError as e:
            rec["error"] = "rate_limited" if e.provider_limited else e.code
        rec["e2e_s"] = time.perf_counter() - t0
        return rec

    for i in range(warmup):
        await one(questions[i % len(questions)])
    records = []
    for i in range(sequential):
        records.append({**await one(questions[i % len(questions)]), "phase": "sequential"})
        r = records[-1]
        print(f"  seq {i + 1}/{sequential}: {r['e2e_s']:.2f}s {'ok' if r['ok'] else r.get('error')}", flush=True)
        await asyncio.sleep(delay)
    sem = asyncio.Semaphore(concurrency)

    async def worker(i):
        async with sem:
            return {**await one(questions[(sequential + i) % len(questions)]), "phase": "concurrent"}

    t0 = time.perf_counter()
    records += await asyncio.gather(*(worker(i) for i in range(concurrent)))
    wall = time.perf_counter() - t0
    print(f"  concurrent x{concurrent} (concurrency {concurrency}) done in {wall:.1f}s", flush=True)
    return summarize_records(records, {"sequential": sequential, "concurrent": concurrent, "concurrency": concurrency,
                                       "warmup": warmup, "delay_s": delay}, "in-process", wall)


# ---------------------------------------------------------------------------
# 3. RAGAS
# ---------------------------------------------------------------------------
def judge_client():
    from openai import AsyncOpenAI

    key = os.environ.get("GROQ_API_KEY")
    if not key:
        from dotenv import load_dotenv

        load_dotenv(ROOT / "backend" / ".env")
        key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise SystemExit("GROQ_API_KEY is required for RAGAS / citation judging")
    return AsyncOpenAI(api_key=key, base_url=GROQ_BASE, max_retries=6, timeout=90)


async def patient(make_call, attempts: int = 8):
    """Retry judge calls on provider rate limits, waiting as long as the 429 asks.

    The free tier's tokens-per-minute cap is easily exceeded by RAGAS (several
    LLM calls per metric), and the client's own short backoff gives up too early.
    """
    from openai import RateLimitError

    for i in range(attempts):
        try:
            return await make_call()
        except RateLimitError as e:
            # A daily quota will not recover within minutes: fail loudly instead of stalling.
            if i == attempts - 1 or "per day" in str(e):
                raise
            m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", str(e))
            wait = (int(m.group(1) or 0) * 60 + float(m.group(2))) if m else 20.0
            await asyncio.sleep(min(wait + 1, 90))


def contexts_for(answer: dict) -> list[str]:
    """The retrieved contexts exactly as the answer model saw them (label, note, text)."""
    from app.api.chat import source_block

    return [source_block(s) for s in answer.get("sources") or []]


async def run_ragas(items: list[dict], answers: dict, judge_model: str, judge_model_2: str | None = None) -> dict:
    from ragas.cache import DiskCacheBackend
    from ragas.embeddings import HuggingFaceEmbeddings
    from ragas.llms import llm_factory
    from ragas.metrics.collections import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness

    # A full run needs ~240K judge tokens for 20 answers, above one free-tier model's
    # 200K/day, which is why scores went missing. Each metric is always judged by the
    # same model; two models share the load. Judge calls are cached on disk.
    cache = DiskCacheBackend(cache_dir=str(EVAL_DIR / ".ragas_cache"))
    llm1 = llm_factory(judge_model, client=judge_client(), max_tokens=4096, temperature=0.0, cache=cache)
    llm2 = (llm_factory(judge_model_2, client=judge_client(), max_tokens=4096, temperature=0.0, cache=cache)
            if judge_model_2 else llm1)
    emb = HuggingFaceEmbeddings(model="sentence-transformers/all-MiniLM-L6-v2")
    metrics = {
        "faithfulness": (Faithfulness(llm=llm1), lambda q, a, c, ref: dict(user_input=q, response=a, retrieved_contexts=c)),
        "answer_relevancy": (AnswerRelevancy(llm=llm2, embeddings=emb), lambda q, a, c, ref: dict(user_input=q, response=a)),
        "context_precision": (ContextPrecision(llm=llm2), lambda q, a, c, ref: dict(user_input=q, reference=ref, retrieved_contexts=c)),
        "context_recall": (ContextRecall(llm=llm1), lambda q, a, c, ref: dict(user_input=q, retrieved_contexts=c, reference=ref)),
    }
    per_item, errors = [], []
    for it in items:
        a = answers.get(it["id"])
        if not it["answerable"] or not a or not a["ok"] or a.get("mode") == "LLM":
            continue
        ctx = contexts_for(a)
        row = {"id": it["id"]}
        for name, (metric, args) in metrics.items():
            try:
                kwargs = args(it["question"], a["answer"], ctx, it["reference_answer"])
                res = await patient(lambda: metric.ascore(**kwargs))
                row[name] = float(res.value)
            except Exception as e:  # recorded, not hidden
                row[name] = None
                errors.append({"id": it["id"], "metric": name, "error": f"{type(e).__name__}: {str(e)[:160]}"})
        print(f"  ragas {it['id']}: " + " ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}=n/a"
                                               for k, v in row.items() if k != "id"), flush=True)
        per_item.append(row)
    scored = {m: sum(r[m] is not None for r in per_item) for m in metrics}
    return {"n": len(per_item), "scored": scored, **{m: mean([r[m] for r in per_item]) for m in metrics},
            "errors": errors, "per_item": per_item}


# ---------------------------------------------------------------------------
# 4. Citation correctness (LLM judge, not a RAGAS metric)
# ---------------------------------------------------------------------------
JUDGE_PROMPT = """You check citations in legal answers.
PASSAGE:
\"\"\"{passage}\"\"\"

CLAIM (a sentence from an answer that cites this passage):
\"\"\"{claim}\"\"\"

Does the passage support the claim's legal content? Minor paraphrase is fine; anything stated in the claim that the passage does not say means NO.
Reply with exactly one word: YES or NO."""


async def citation_correctness(items: list[dict], answers: dict, judge_model: str, n_answers: int = 10) -> dict:
    client = judge_client()
    pairs, checked = [], 0
    for it in items:
        a = answers.get(it["id"])
        if checked >= n_answers or not it["answerable"] or not a or not a["ok"] or not a["citations"]:
            continue
        checked += 1
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", a["answer"]):
            for n in sorted({int(x) for x in re.findall(r"\[(\d{1,2})\]", sentence)}):
                if 1 <= n <= len(a["sources"]):
                    pairs.append((it["id"], re.sub(r"\[\d{1,2}\]", "", sentence).strip(), contexts_for(a)[n - 1]))
    verdicts = []
    for item_id, claim, passage in pairs:
        try:
            r = await patient(lambda: client.chat.completions.create(
                model=judge_model, temperature=0, max_tokens=512,
                messages=[{"role": "user", "content": JUDGE_PROMPT.format(passage=passage, claim=claim)}],
                extra_body=({"reasoning_effort": "low", "include_reasoning": False} if "gpt-oss" in judge_model
                            else {"reasoning_format": "hidden"} if "qwen" in judge_model else None),
            ))
            text = (r.choices[0].message.content or "").strip().upper()
            verdict = True if text.startswith("YES") else False if text.startswith("NO") else None
        except Exception as e:
            verdict = None
            text = f"error: {type(e).__name__}"
        verdicts.append({"id": item_id, "claim": claim[:200], "supported": verdict, "raw": text[:20]})
    judged = [v for v in verdicts if v["supported"] is not None]
    return {"answers_checked": checked, "citations_checked": len(judged), "unjudged": len(verdicts) - len(judged),
            "citation_correctness": round(sum(v["supported"] for v in judged) / len(judged), 3) if judged else None,
            "per_citation": verdicts}


# Heuristic only: does the answer to an unanswerable question say the sources don't cover it?
_DECLINE = re.compile(r"(do(es)? not|don't|doesn't|not)\s+(contain|cover|include|address|mention|provide|have|answer|specify|state|give|say)|"
                      r"no (relevant )?(information|provision)|cannot (find|answer)|not (available|found) in", re.I)


def unanswerable_handling(items, answers) -> dict:
    rows = [{"id": i["id"], "answered": bool(answers.get(i["id"], {}).get("ok")),
             "declined": bool(answers.get(i["id"], {}).get("ok") and _DECLINE.search(answers[i["id"]]["answer"]))}
            for i in items if not i["answerable"]]
    answered = [r for r in rows if r["answered"]]  # failed requests are not counted as "did not decline"
    return {"n": len(rows), "answered": len(answered),
            "declined_rate": mean([float(r["declined"]) for r in answered]), "per_item": rows}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def fmt(v, suffix=""):
    return "n/a" if v is None else f"{v:.3f}{suffix}" if isinstance(v, float) else f"{v}{suffix}"


def comparison(baseline: dict | None, after: dict | None) -> list[tuple]:
    if not baseline or not after:
        return []
    rows = []
    for label, key in [("p50 latency (s)", "p50_s"), ("p95 latency (s)", "p95_s"), ("mean latency (s)", "mean_s"),
                       ("error rate", "error_rate")]:
        b, a = baseline["overall"].get(key), after["overall"].get(key)
        change = f"{(a - b) / b:+.0%}" if b and a is not None else "n/a"
        rows.append((label, b, a, change))
    return rows


def write_reports(res: dict) -> None:
    (EVAL_DIR / "results.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    md = [f"# LawTalk evaluation results", "", f"Run: {res['timestamp']}  ", f"Config: `{json.dumps(res['config'])}`", "",
          "| Metric | Value | Notes |", "|---|---|---|"]
    for k, v in res["summary"].items():
        md.append(f"| {k} | {fmt(v)} | {res['notes'].get(k, '')} |")
    if res.get("comparison"):
        md += ["", "## Latency before / after", "", "| Metric | Before | After | Change |", "|---|---|---|---|"]
        md += [f"| {l} | {fmt(b)} | {fmt(a)} | {c} |" for l, b, a, c in res["comparison"]]
    md += ["", "## Caveats", ""] + [f"- {c}" for c in res["caveats"]]
    (EVAL_DIR / "results.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    update_readme(res)


README_KEYS = ["Faithfulness", "Answer relevancy", "Context precision", "Context recall", "Retrieval Recall@5",
               "Retrieval Hit@5", "Citation correctness", "TTFT p50 (s)", "p95 latency (s)", "Request error rate",
               "App error rate", "Provider rate-limited"]


def update_readme(res: dict) -> None:
    """Rewrite the metrics block between the EVAL markers in README.md from this run."""
    path = ROOT / "README.md"
    start, end = "<!-- EVAL:START -->", "<!-- EVAL:END -->"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if start not in text or end not in text:
        return
    rows = ["| Metric | Result | Measured on |", "|---|---|---|"]
    rows += [f"| {k} | {fmt(res['summary'].get(k))} | {res['notes'].get(k, '')} |" for k in README_KEYS]
    extra = [k for k in res["summary"] if k not in README_KEYS]
    rows += [f"| {k} | {fmt(res['summary'].get(k))} | {res['notes'].get(k, '')} |" for k in extra]
    block = [start, f"_Last run: {res['timestamp']} — generated by `eval/run_eval.py` from `eval/results.json`._", ""]
    block += [f"> **Note:** {c}" for c in res.get("caveats", []) if c.startswith("This run hit")] + [""] * any(
        c.startswith("This run hit") for c in res.get("caveats", []))
    block += rows
    if res.get("comparison"):
        block += ["", "**Latency before / after** (same 50-request benchmark: 30 sequential + 20 concurrent, `/ask`)", "",
                  "| | Before (original code) | After | Change |", "|---|---|---|---|"]
        block += [f"| {l} | {fmt(b)} | {fmt(a)} | {c} |" for l, b, a, c in res["comparison"]]
    block.append(end)
    pre, rest = text.split(start, 1)
    post = rest.split(end, 1)[1]
    path.write_text(pre + "\n".join(block) + post, encoding="utf-8")


def print_table(res: dict) -> None:
    w = max(len(k) for k in res["summary"]) + 2
    print("\n" + "=" * 64 + "\n LawTalk evaluation\n" + "=" * 64)
    for k, v in res["summary"].items():
        print(f" {k:<{w}} {fmt(v):>10}   {res['notes'].get(k, '')}")
    if res.get("comparison"):
        print("-" * 64 + f"\n {'Latency':<20}{'before':>10}{'after':>10}{'change':>10}")
        for l, b, a, c in res["comparison"]:
            print(f" {l:<20}{fmt(b):>10}{fmt(a):>10}{c:>10}")
    print("=" * 64)


async def benchmark_only(base: str, items: list[dict], in_process: bool = False) -> None:
    """Re-measure latency and update only the latency fields of eval/results.json."""
    path = EVAL_DIR / "results.json"
    if not path.exists():
        raise SystemExit("eval/results.json not found: run a full evaluation first")
    res = json.loads(path.read_text(encoding="utf-8"))
    print("benchmark: 30 sequential + 20 concurrent requests to /ask")
    bench = (await benchmark_inprocess([i["question"] for i in items]) if in_process
             else await run_benchmark(base, [i["question"] for i in items], headers=auth_headers()))
    baseline_path = EVAL_DIR / "baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.exists() else None
    res["summary"]["p95 latency (s)"] = bench["overall"]["p95_s"]
    res["summary"]["Request error rate"] = bench["overall"]["error_rate"]
    res["notes"]["p95 latency (s)"] = f"{bench['overall']['requests']} requests (re-measured {time.strftime('%Y-%m-%d %H:%M')})"
    res["notes"]["Request error rate"] = f"errors: {bench['errors_by_type']}"
    res["comparison"] = comparison(baseline, bench)
    res["details"]["benchmark"] = bench
    annotate(res)
    write_reports(res)
    print_table(res)


async def main_async(args) -> None:
    items = json.loads((EVAL_DIR / "testset.json").read_text(encoding="utf-8"))
    if args.limit:  # smoke test: a few answerable + one unanswerable item
        items = [i for i in items if i["answerable"]][: args.limit] + [i for i in items if not i["answerable"]][:1]
    base = args.base_url.rstrip("/")
    if not args.in_process:
        async with httpx.AsyncClient() as c:
            try:
                (await c.get(base + "/health", timeout=5)).raise_for_status()
            except httpx.HTTPError:
                raise SystemExit(f"Backend not reachable at {base}. Start it with: cd backend && uvicorn app.main:app")
            # Check the token up front (no LLM call), so an expired token can't waste a run.
            r = await c.get(base + "/auth/check", headers=auth_headers(), timeout=15)
            if r.status_code != 200:
                detail = (r.json().get("detail") or {}) if r.headers.get("content-type", "").startswith("application/json") else {}
                raise SystemExit(f"EVAL_AUTH_TOKEN was rejected ({r.status_code}: {detail.get('message', r.text[:120])}). "
                                 "Tokens expire after about an hour; get a fresh one with `python eval/get_token.py`.")
    else:
        from app.services import rag

        rag.load_db()

    if args.benchmark_only:
        await benchmark_only(base, items, args.in_process)
        return

    print("1/4 retrieval recall@5")
    retrieval = retrieval_recall(items)
    print(f"  recall@5={retrieval['recall_at_5']} hit@5={retrieval['hit_rate_at_5']} (n={retrieval['n']})")

    # Latency first and alone, so it is measured the same way as eval/baseline.json
    # (no judge traffic in parallel, provider rate-limit budget not already spent).
    bench = None
    if not args.skip_benchmark:
        print("2/4 benchmark: 30 sequential + 20 concurrent requests" + (" (in-process)" if args.in_process else " to /ask"))
        bench = (await benchmark_inprocess([i["question"] for i in items]) if args.in_process
                 else await run_benchmark(base, [i["question"] for i in items], headers=auth_headers()))
        await asyncio.sleep(60)  # let the tokens-per-minute window refill

    print("3/4 generating answers" + (" (in-process)" if args.in_process else " via /ask/stream"))
    gen = (await generate_answers_inprocess(items, args.delay) if args.in_process
           else await generate_answers(base, items, args.delay))
    answers = {g["id"]: g for g in gen}

    ragas = cites = None
    if not args.skip_ragas:
        print(f"4/4 RAGAS + citation judge (judges: {args.judge_model}, {args.judge_model_2})")
        ragas = await run_ragas(items, answers, args.judge_model, args.judge_model_2)
        cites = await citation_correctness(items, answers, args.judge_model)

    baseline_path = EVAL_DIR / "baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.exists() else None
    ttft = sorted(g["ttft_s"] for g in gen if g.get("ttft_s"))
    modes = {m: sum(1 for g in gen if g.get("mode") == m) for m in ("RAG", "LLM")}
    res = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "config": {"judge_models": {"faithfulness": args.judge_model, "context_recall": args.judge_model,
                                    "answer_relevancy": args.judge_model_2 or args.judge_model,
                                    "context_precision": args.judge_model_2 or args.judge_model,
                                    "citation_correctness": args.judge_model},
                   "testset": "eval/testset.json", "n_questions": len(items),
                   "transport": "in-process (no HTTP/auth)" if args.in_process else "HTTP (/ask/stream, /ask)"},
        "summary": {
            "Faithfulness": ragas and ragas["faithfulness"],
            "Answer relevancy": ragas and ragas["answer_relevancy"],
            "Context precision": ragas and ragas["context_precision"],
            "Context recall": ragas and ragas["context_recall"],
            "Retrieval Recall@5": retrieval["recall_at_5"],
            "Retrieval Hit@5": retrieval["hit_rate_at_5"],
            "Citation correctness": cites and cites["citation_correctness"],
            "Unanswerable declined": unanswerable_handling(items, answers)["declined_rate"],
            "TTFT p50 (s)": round(ttft[len(ttft) // 2], 3) if ttft else None,
            "p95 latency (s)": bench and bench["overall"]["p95_s"],
            "Request error rate": bench and bench["overall"]["error_rate"],
            "App error rate": bench and bench["overall"]["app_error_rate"],
            "Provider rate-limited": bench and bench["overall"]["provider_rate_limited_rate"],
            "Routed to RAG": f"{modes['RAG']}/{len(gen)}",
        },
        "notes": {
            "Faithfulness": "RAGAS",
            "Answer relevancy": "RAGAS (MiniLM embeddings)",
            "Context precision": "RAGAS, with reference",
            "Context recall": "RAGAS",
            "Retrieval Recall@5": f"labelled chunk IDs, n={retrieval['n']}",
            "Retrieval Hit@5": ">=1 labelled chunk in top 5",
            "Citation correctness": (f"LLM judge, {cites['citations_checked']} citations in {cites['answers_checked']} answers"
                                     if cites else ""),
            "Unanswerable declined": f"keyword heuristic, n={sum(not i['answerable'] for i in items)}",
            "TTFT p50 (s)": f"streamed answers, n={len(ttft)}",
            "p95 latency (s)": f"{bench['overall']['requests']} requests, {bench['endpoint']}" if bench else "",
            "Request error rate": f"all failures: {bench['errors_by_type']}" if bench else "",
            "App error rate": "failures not caused by provider limits" if bench else "",
            "Provider rate-limited": "Groq 429s that survived retries and pacing" if bench else "",
            "Routed to RAG": "all 25 test questions are legal",
        },
        "comparison": comparison(baseline, bench),
        "details": {"retrieval": retrieval, "ragas": ragas, "citations": cites, "answers": gen,
                    "benchmark": bench, "baseline": baseline,
                    "unanswerable": unanswerable_handling(items, answers)},
        "caveats": [
            "Reference answers and relevance labels were drafted by an AI assistant from the indexed text and have not been reviewed by a lawyer.",
            "25 questions: small-sample metrics, useful for regressions rather than absolute claims.",
            "LLM-judged metrics (RAGAS, citation correctness) depend on the judge model and can vary between runs.",
            "Latency depends on the Groq free tier (8K tokens/minute); the client paces requests to stay under it.",
            "The latency benchmark runs first and alone; quality metrics run afterwards.",
        ] + (["In-process run: same router, retrieval, prompt and Groq code as the API, without HTTP or the auth check."]
             if args.in_process else []),
    }
    annotate(res)
    write_reports(res)
    print_table(res)
    print(f"wrote {EVAL_DIR / 'results.json'} and {EVAL_DIR / 'results.md'}")


def annotate(res: dict) -> None:
    """Make the notes state exactly what was measured, and flag provider-limit failures."""
    d = res["details"]
    ragas, cites, answers, bench = d.get("ragas"), d.get("citations"), d.get("answers") or [], d.get("benchmark")
    if ragas:
        scored = ragas.get("scored") or {m: sum(r.get(m) is not None for r in ragas["per_item"])
                                         for m in ("faithfulness", "answer_relevancy", "context_precision", "context_recall")}
        for key, m in [("Faithfulness", "faithfulness"), ("Answer relevancy", "answer_relevancy"),
                       ("Context precision", "context_precision"), ("Context recall", "context_recall")]:
            res["notes"][key] = f"RAGAS, scored {scored[m]}/{ragas['n']} answers"
    un = d.get("unanswerable")
    if un:
        answered = un.get("answered", sum(r.get("answered", True) for r in un["per_item"]))
        res["notes"]["Unanswerable declined"] = f"keyword heuristic, {answered}/{un['n']} answered"
    failed_answers = sum(not a["ok"] for a in answers)
    judge_failures = len(ragas["errors"]) if ragas else 0
    unjudged = cites["unjudged"] if cites else 0
    limits = [c for c in res["caveats"] if c.startswith("This run hit")]
    for c in limits:
        res["caveats"].remove(c)
    if failed_answers or judge_failures or unjudged or (bench and bench["overall"]["errors"]):
        res["caveats"].insert(0, (
            f"This run hit provider rate/daily limits: {failed_answers} answer requests failed, {judge_failures} RAGAS "
            f"metric calls and {unjudged} citation checks could not be judged, and "
            f"{bench['overall']['errors'] if bench else 0} benchmark requests returned errors. Scores cover only what was "
            "measured; re-run with fresh quota for complete numbers."))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--judge-model", default="qwen/qwen3.8-27b", help="faithfulness, context recall, citations")
    ap.add_argument("--judge-model-2", default="openai/gpt-oss-20b", help="answer relevancy, context precision")
    ap.add_argument("--in-process", action="store_true",
                    help="call the pipeline directly (no HTTP/auth) when no EVAL_AUTH_TOKEN is available")
    ap.add_argument("--delay", type=float, default=3.0, help="seconds between answer requests (rate limits)")
    ap.add_argument("--limit", type=int, help="smoke test with N answerable questions (results still written)")
    ap.add_argument("--skip-ragas", action="store_true")
    ap.add_argument("--skip-benchmark", action="store_true")
    ap.add_argument("--benchmark-only", action="store_true", help="re-measure latency; keep other results")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
