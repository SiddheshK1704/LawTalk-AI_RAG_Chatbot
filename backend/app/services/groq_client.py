import asyncio
import logging
import time
from collections import deque

import groq
import httpx
from groq import AsyncGroq

from app.core.config import (
    GROQ_API_KEY, GROQ_MAX_RETRIES, GROQ_MAX_TOKENS, GROQ_MODEL, GROQ_REASONING_EFFORT, GROQ_TIMEOUT_S,
    GROQ_MAX_QUEUE_S, GROQ_TPM_BUDGET, LLM_MAX_CONCURRENCY,
)

logger = logging.getLogger("lawtalk")

# One client per process: connection pooling, bounded timeout, retries that honour
# the provider's retry-after header on 429.
client = AsyncGroq(
    api_key=GROQ_API_KEY,
    timeout=httpx.Timeout(GROQ_TIMEOUT_S, connect=5.0),
    max_retries=GROQ_MAX_RETRIES,
)
_slots = asyncio.Semaphore(LLM_MAX_CONCURRENCY)


class LLMError(Exception):
    def __init__(self, code: str, message: str, status: int):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status

    @property
    def provider_limited(self) -> bool:
        return self.code == "rate_limited"


class TokenBudget:
    """Client-side tokens-per-minute pacing.

    Every error in the benchmarks was Groq's TPM 429 (free tier: 8,000 tokens/minute).
    Instead of sending a request that will be rejected, wait until the last 60 s of
    usage leaves room for it. Estimates are replaced by real usage once known.
    """

    def __init__(self, tpm: int):
        self.tpm = tpm
        self.events: deque[list] = deque()  # [timestamp, tokens]
        self.lock = asyncio.Lock()

    def _used(self, now: float) -> int:
        while self.events and now - self.events[0][0] >= 60:
            self.events.popleft()
        return sum(t for _, t in self.events)

    async def acquire(self, estimate: int, max_wait: float = float("inf")) -> list:
        """Reserve tokens, waiting for room. If the wait would exceed ``max_wait`` seconds,
        fail fast with a rate-limit error instead of leaving the user waiting silently."""
        async with self.lock:
            deadline = time.monotonic() + max_wait
            while True:
                now = time.monotonic()
                if self._used(now) + estimate <= self.tpm or not self.events:
                    entry = [now, estimate]
                    self.events.append(entry)
                    return entry
                wait = max(0.2, 60 - (now - self.events[0][0]))
                if now + wait > deadline:
                    raise LLMError("rate_limited", f"The AI service is busy right now. Please try again in about {int(wait)} seconds.", 503)
                await asyncio.sleep(wait)

    @staticmethod
    def settle(entry: list, actual: int | None) -> None:
        if actual:
            entry[1] = actual


_budget = TokenBudget(GROQ_TPM_BUDGET) if GROQ_TPM_BUDGET > 0 else None


def _estimate(messages: list[dict]) -> int:
    chars = sum(len(m.get("content", "")) for m in messages)
    return int(chars / 3.5) + 450  # prompt + a typical answer incl. reasoning


def _map_error(e: Exception) -> LLMError:
    if isinstance(e, groq.RateLimitError):
        return LLMError("rate_limited", "The AI service is busy right now. Please try again in a moment.", 503)
    if isinstance(e, (groq.APITimeoutError, httpx.TimeoutException)):
        return LLMError("timeout", "The AI service took too long to respond. Please try again.", 504)
    if isinstance(e, groq.APIConnectionError):
        return LLMError("unavailable", "Could not reach the AI service. Please try again.", 502)
    return LLMError("llm_error", "The AI service returned an error. Please try again.", 502)


def _params(messages: list[dict], max_tokens: int | None = None) -> dict:
    params = {"model": GROQ_MODEL, "messages": messages, "temperature": 0.2,
              "max_completion_tokens": max_tokens or GROQ_MAX_TOKENS}
    if GROQ_REASONING_EFFORT and "gpt-oss" in GROQ_MODEL:
        params.update(reasoning_effort=GROQ_REASONING_EFFORT, include_reasoning=False)
    return params


async def _reserve(messages: list[dict], timer) -> list | None:
    if _budget is None:
        return None
    t = time.perf_counter()
    entry = await _budget.acquire(_estimate(messages), GROQ_MAX_QUEUE_S)
    waited = time.perf_counter() - t
    if timer is not None and waited > 0.001:
        timer.add("llm_queue", waited)
    return entry


async def get_llm_response(messages: list[dict], timer=None, max_tokens: int | None = None) -> str:
    t0 = time.perf_counter()
    async with _slots:
        entry = await _reserve(messages, timer)
        try:
            resp = await client.chat.completions.create(**_params(messages, max_tokens))
        except Exception as e:  # mapped to a user-safe error
            logger.warning("[LLM] %s: %s", type(e).__name__, str(e)[:200])
            raise _map_error(e) from e
    if entry is not None:
        TokenBudget.settle(entry, getattr(resp.usage, "total_tokens", None))
    if timer is not None:
        timer.add("llm_total", time.perf_counter() - t0)
    return resp.choices[0].message.content or ""


async def stream_llm_response(messages: list[dict], timer=None, max_tokens: int | None = None):
    """Yield text deltas. Closing the generator closes the upstream stream.
    llm_first_token and llm_total include any time spent waiting for TPM budget."""
    t0 = time.perf_counter()
    first = True
    async with _slots:
        entry = await _reserve(messages, timer)
        try:
            stream = await client.chat.completions.create(**_params(messages, max_tokens), stream=True)
        except Exception as e:
            logger.warning("[LLM] %s: %s", type(e).__name__, str(e)[:200])
            raise _map_error(e) from e
        usage = None
        try:
            async for chunk in stream:
                x = getattr(chunk, "x_groq", None)
                if x is not None and getattr(x, "usage", None):
                    usage = getattr(x.usage, "total_tokens", None)
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    if first and timer is not None:
                        timer.add("llm_first_token", time.perf_counter() - t0)
                    first = False
                    yield delta
        except Exception as e:
            logger.warning("[LLM] stream %s: %s", type(e).__name__, str(e)[:200])
            raise _map_error(e) from e
        finally:
            await stream.close()
            if entry is not None:
                TokenBudget.settle(entry, usage)
            if timer is not None:
                timer.add("llm_total", time.perf_counter() - t0)
