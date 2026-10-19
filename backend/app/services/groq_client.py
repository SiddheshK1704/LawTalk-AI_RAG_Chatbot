import asyncio
import logging
import time

import groq
import httpx
from groq import AsyncGroq

from app.core.config import (
    GROQ_API_KEY, GROQ_MAX_RETRIES, GROQ_MAX_TOKENS, GROQ_MODEL, GROQ_REASONING_EFFORT, GROQ_TIMEOUT_S, LLM_MAX_CONCURRENCY,
)

logger = logging.getLogger("lawtalk")

# One client per process: connection pooling, bounded timeout, retries that honour
# the provider's retry-after header on 429 (free-tier token limits are the usual cause).
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


def _map_error(e: Exception) -> LLMError:
    if isinstance(e, groq.RateLimitError):
        return LLMError("rate_limited", "The AI service is busy right now. Please try again in a moment.", 503)
    if isinstance(e, (groq.APITimeoutError, httpx.TimeoutException)):
        return LLMError("timeout", "The AI service took too long to respond. Please try again.", 504)
    if isinstance(e, groq.APIConnectionError):
        return LLMError("unavailable", "Could not reach the AI service. Please try again.", 502)
    return LLMError("llm_error", "The AI service returned an error. Please try again.", 502)


def _params(messages: list[dict]) -> dict:
    params = {"model": GROQ_MODEL, "messages": messages, "temperature": 0.2,
              "max_completion_tokens": GROQ_MAX_TOKENS}
    if GROQ_REASONING_EFFORT and "gpt-oss" in GROQ_MODEL:
        params.update(reasoning_effort=GROQ_REASONING_EFFORT, include_reasoning=False)
    return params


async def get_llm_response(messages: list[dict], timer=None) -> str:
    t0 = time.perf_counter()
    async with _slots:
        try:
            resp = await client.chat.completions.create(**_params(messages))
        except Exception as e:  # mapped to a user-safe error
            logger.warning("[LLM] %s: %s", type(e).__name__, str(e)[:200])
            raise _map_error(e) from e
    if timer is not None:
        timer.add("llm_total", time.perf_counter() - t0)
    return resp.choices[0].message.content or ""


async def stream_llm_response(messages: list[dict], timer=None):
    """Yield text deltas. Closing the generator closes the upstream stream."""
    t0 = time.perf_counter()
    first = True
    async with _slots:
        try:
            stream = await client.chat.completions.create(**_params(messages), stream=True)
        except Exception as e:
            logger.warning("[LLM] %s: %s", type(e).__name__, str(e)[:200])
            raise _map_error(e) from e
        try:
            async for chunk in stream:
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
            if timer is not None:
                timer.add("llm_total", time.perf_counter() - t0)
