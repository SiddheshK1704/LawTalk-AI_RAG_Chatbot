"""Terminal-only request metrics.

Every request logs one line, e.g.
    [REQ] embed=0.015s retrieve=0.001s llm_first_token=0.62s llm_total=1.80s e2e=1.83s status=200
and a rolling summary is printed every METRICS_SUMMARY_EVERY requests and on shutdown.
Nothing here is sent to the frontend.
"""
import json
import logging
import math
import os
import sys
import threading
import time
from collections import deque

from app.core.config import BASE_DIR, METRICS_SUMMARY_EVERY

logger = logging.getLogger("lawtalk")
if not logger.handlers:  # uvicorn only configures its own loggers
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)
    logger.propagate = False

STAGES = ("embed", "retrieve", "llm_first_token", "llm_total")


class RequestTimer:
    def __init__(self):
        self.t0 = time.perf_counter()
        self.stages: dict[str, float] = {}

    def add(self, name: str, seconds: float) -> None:
        self.stages[name] = self.stages.get(name, 0.0) + seconds

    def since_start(self) -> float:
        return time.perf_counter() - self.t0


def _pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


class MetricsTracker:
    def __init__(self, window: int = 500, every: int = METRICS_SUMMARY_EVERY):
        self.window = deque(maxlen=window)
        self.every = every
        self.total = 0
        self.errors = 0
        self._lock = threading.Lock()

    def record(self, timer: RequestTimer, status: int, path: str = "/ask") -> None:
        e2e = timer.since_start()
        parts = [f"{s}={timer.stages[s]:.3f}s" for s in STAGES if s in timer.stages]
        logger.info("[REQ] %s", " ".join([path, *parts, f"e2e={e2e:.3f}s", f"status={status}"]))
        with self._lock:
            self.total += 1
            self.errors += status >= 400
            self.window.append({"e2e": e2e, "status": status, **timer.stages})
            due = self.every > 0 and self.total % self.every == 0
        if due:
            self.print_summary()

    def print_summary(self, reason: str = "") -> None:
        with self._lock:
            rows = list(self.window)
            total, errors = self.total, self.errors
        if not rows:
            logger.info("[METRICS] no requests recorded%s", f" ({reason})" if reason else "")
            return
        ok = [r["e2e"] for r in rows if r["status"] < 400]
        avg = {s: sum(r[s] for r in rows if s in r) / max(1, sum(s in r for r in rows)) for s in STAGES}
        lines = [
            f"==================== LawTalk metrics{' (' + reason + ')' if reason else ''} ====================",
            f"requests={total}  errors={errors}  error_rate={errors / total:.1%}  (window: last {len(rows)})",
            (f"e2e   p50={_pct(ok, 50):.3f}s  p95={_pct(ok, 95):.3f}s  mean={sum(ok) / len(ok):.3f}s"
             if ok else "e2e   no successful requests in window"),
            "avg   " + "  ".join(f"{s}={avg[s]:.3f}s" for s in STAGES if any(s in r for r in rows)),
            "=" * 72,
        ]
        logger.info("\n" + "\n".join(lines))


tracker = MetricsTracker()


def print_eval_banner() -> None:
    """Show the latest saved evaluation results (eval/results.json), if any."""
    path = os.path.join(os.path.dirname(BASE_DIR), "eval", "results.json")
    if not os.path.exists(path):
        logger.info("[EVAL] no eval/results.json yet - run: python eval/run_eval.py")
        return
    try:
        with open(path, encoding="utf-8") as f:
            res = json.load(f)
    except (OSError, ValueError) as e:
        logger.warning("[EVAL] could not read eval/results.json: %s", e)
        return
    lines = [f"==================== Latest evaluation ({res.get('timestamp', '?')}) ===================="]
    for name, value in res.get("summary", {}).items():
        lines.append(f"  {name:<28} {value if value is not None else 'n/a'}")
    lines.append("=" * 72)
    logger.info("\n" + "\n".join(lines))
