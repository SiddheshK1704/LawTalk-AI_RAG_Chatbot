"""HTTP latency benchmark: ~50 requests, part sequential and part concurrent.

Works against the original backend (POST /ask -> {"answer"}) and the new one, so
before/after numbers come from the same client and the same questions.

    python eval/benchmark.py --base-url http://127.0.0.1:8001 --label baseline
"""
import argparse
import asyncio
import json
import math
import os
import time
from pathlib import Path

import httpx

EVAL_DIR = Path(__file__).resolve().parent


def auth_headers(required: bool = True) -> dict:
    """Bearer token for the API from EVAL_AUTH_TOKEN (a Supabase access token).

    Get one with `python eval/get_token.py`. The original backend had no auth and
    simply ignores the header, so the same benchmark works for the baseline.
    """
    token = os.environ.get("EVAL_AUTH_TOKEN", "").strip()
    if not token and required:
        raise SystemExit("EVAL_AUTH_TOKEN is not set. Get a token with `python eval/get_token.py` "
                         "(see eval/README.md) and export it before running.")
    return {"Authorization": f"Bearer {token}"} if token else {}


def percentile(xs: list[float], p: float) -> float | None:
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


async def _one(client: httpx.AsyncClient, base: str, q: str, stream: bool, timeout: float, headers: dict) -> dict:
    t0 = time.perf_counter()
    rec = {"ok": False, "stream": stream}
    try:
        if stream:
            async with client.stream("POST", base + "/ask/stream", json={"query": q}, headers=headers, timeout=timeout) as r:
                rec["status"] = r.status_code
                event = None
                async for line in r.aiter_lines():
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        if event == "token" and "ttft_s" not in rec:
                            rec["ttft_s"] = time.perf_counter() - t0
                        elif event == "done":
                            rec["ok"] = r.status_code == 200
                        elif event == "error":
                            rec["error"] = json.loads(line[5:]).get("code", "error")
        else:
            r = await client.post(base + "/ask", json={"query": q}, headers=headers, timeout=timeout)
            rec["status"] = r.status_code
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            rec["ok"] = r.status_code == 200 and bool(body.get("answer"))
            if not rec["ok"]:
                detail = body.get("detail") if isinstance(body.get("detail"), dict) else {}
                rec["error"] = detail.get("code") or f"http_{r.status_code}"
    except httpx.TimeoutException:
        rec["error"] = "timeout"
    except httpx.HTTPError as e:
        rec["error"] = type(e).__name__
    rec["e2e_s"] = time.perf_counter() - t0
    return rec


async def run_benchmark(base_url: str, questions: list[str], sequential: int = 30, concurrent: int = 20,
                        concurrency: int = 4, stream: bool = False, timeout: float = 120.0,
                        warmup: int = 2, delay: float = 2.0, headers: dict | None = None) -> dict:
    base = base_url.rstrip("/")
    headers = auth_headers(required=False) if headers is None else headers
    async with httpx.AsyncClient() as client:
        for i in range(warmup):  # not counted: first requests pay one-off costs
            await _one(client, base, questions[i % len(questions)], stream, timeout, headers)
        records = []
        for i in range(sequential):
            records.append({**await _one(client, base, questions[i % len(questions)], stream, timeout, headers), "phase": "sequential"})
            print(f"  seq {i + 1}/{sequential}: {records[-1]['e2e_s']:.2f}s {'ok' if records[-1]['ok'] else records[-1].get('error')}", flush=True)
            await asyncio.sleep(delay)
        sem = asyncio.Semaphore(concurrency)

        async def worker(i: int):
            async with sem:
                return {**await _one(client, base, questions[(sequential + i) % len(questions)], stream, timeout, headers), "phase": "concurrent"}

        t0 = time.perf_counter()
        conc = await asyncio.gather(*(worker(i) for i in range(concurrent)))
        conc_wall = time.perf_counter() - t0
        records.extend(conc)
        print(f"  concurrent x{concurrent} (concurrency {concurrency}) done in {conc_wall:.1f}s", flush=True)

    out = summarize_records(records, {"sequential": sequential, "concurrent": concurrent, "concurrency": concurrency,
                                      "warmup": warmup, "delay_s": delay}, "/ask/stream" if stream else "/ask", conc_wall)
    out["base_url"] = base
    return out


# Provider refusals. The original backend surfaced Groq 429s as plain HTTP 500s, which
# this client cannot tell apart from crashes, so those are reported as http_500.
PROVIDER_LIMIT_CODES = {"rate_limited"}


def summarize_records(records: list[dict], config: dict, endpoint: str, conc_wall: float) -> dict:
    def stats(rs):
        ok = [r["e2e_s"] for r in rs if r["ok"]]
        ttft = [r["ttft_s"] for r in rs if r.get("ttft_s")]
        limited = sum(1 for r in rs if not r["ok"] and r.get("error") in PROVIDER_LIMIT_CODES)
        failed = sum(not r["ok"] for r in rs)
        n = max(1, len(rs))
        return {
            "requests": len(rs),
            "errors": failed,
            "error_rate": round(failed / n, 3),                      # all failures (comparable with old runs)
            "provider_rate_limited": limited,
            "provider_rate_limited_rate": round(limited / n, 3),
            "app_errors": failed - limited,
            "app_error_rate": round((failed - limited) / n, 3),      # failures not caused by provider limits
            "p50_s": round(percentile(ok, 50), 3) if ok else None,
            "p95_s": round(percentile(ok, 95), 3) if ok else None,
            "mean_s": round(sum(ok) / len(ok), 3) if ok else None,
            "ttft_p50_s": round(percentile(ttft, 50), 3) if ttft else None,
        }

    errors = {}
    for r in records:
        if not r["ok"]:
            errors[r.get("error", "unknown")] = errors.get(r.get("error", "unknown"), 0) + 1
    return {
        "endpoint": endpoint,
        "config": config,
        "overall": stats(records),
        "sequential": stats([r for r in records if r["phase"] == "sequential"]),
        "concurrent": {**stats([r for r in records if r["phase"] == "concurrent"]), "wall_s": round(conc_wall, 2)},
        "errors_by_type": errors,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--label", default="run", help="'baseline' is saved to eval/baseline.json")
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--sequential", type=int, default=30)
    ap.add_argument("--concurrent", type=int, default=20)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--no-auth", action="store_true", help="for the original backend, which had no auth")
    args = ap.parse_args()
    questions = [i["question"] for i in json.loads((EVAL_DIR / "testset.json").read_text(encoding="utf-8"))]
    result = asyncio.run(run_benchmark(args.base_url, questions, args.sequential, args.concurrent,
                                       args.concurrency, args.stream, headers=auth_headers(not args.no_auth)))
    result["label"] = args.label
    result["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    out = EVAL_DIR / ("baseline.json" if args.label == "baseline" else f"benchmark-{args.label}.json")
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["overall"], indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
