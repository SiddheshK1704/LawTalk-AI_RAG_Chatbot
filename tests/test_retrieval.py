"""Retrieval behaviour that the evaluation depends on."""
import asyncio
import time

import pytest
from _support import needs_index

from app.services.ingest import detect_headers, repair_split_words
from collections import Counter
from concurrent.futures import ThreadPoolExecutor


def run_async(coro_fn):
    """Run a coroutine on its own thread/loop (Playwright's sync API may own the main loop)."""
    with ThreadPoolExecutor(1) as ex:
        return ex.submit(lambda: asyncio.run(coro_fn())).result()


def test_word_repair_is_conservative():
    vocab = Counter({"shall": 500, "sha": 1, "ll": 1, "unlawful": 40, "unla": 1, "wful": 1, "in": 900, "deed": 30, "indeed": 5})
    assert repair_split_words("murder sha ll be punished in the unla wful assembly", vocab) == \
        "murder shall be punished in the unlawful assembly"
    assert repair_split_words("in deed", vocab) == "in deed"  # real word pair left alone


def test_header_detection_ignores_schedules_and_footnotes():
    text = ("1. Short title.—This Act. 2. Definitions.—In this Act. 3. Punishment.—Whoever.\n"
            "4. Ins. by Act 5 of 2001, s. 2 (w.e.f. 1-1-2002).\n\n"
            "Right to Remedies 4. Remedies for enforcement.—(1) The right. 5. Saving.—Nothing.\n"
            "SCHEDULE 1. Paragraph one.—Text. 2. Paragraph two.—Text.")
    nums = [n for _, n, _ in detect_headers(text)]
    assert nums == ["1", "2", "3", "4", "5"], nums


@needs_index
def test_article_lookup_returns_the_article_not_a_schedule(rag):
    sources = rag.retrieve("What does Article 21 of the Constitution provide?")
    assert sources[0]["title"].startswith("Constitution") and sources[0]["section"] in ("20", "21")
    assert "deprived of his life or personal liberty" in " ".join(s["text"] for s in sources[:2])


@needs_index
def test_definition_lookup(rag):
    text = " ".join(s["text"] for s in rag.retrieve("Who is a child under the POCSO Act?"))
    assert "below the age of eighteen years" in text


@needs_index
def test_sources_carry_real_metadata_only(rag):
    for s in rag.retrieve("What is the punishment for murder under the Indian Penal Code?"):
        assert s["chunk_id"] and s["text"]
        if s["page"] is not None:
            assert isinstance(s["page"], int) and s["page"] >= 1


def test_token_budget_waits_instead_of_exceeding():
    from app.services.groq_client import TokenBudget

    async def run():
        b = TokenBudget(1000)
        await b.acquire(800)
        t = time.monotonic()
        b.events[0][0] -= 59.7  # pretend the first request was ~60 s ago
        await b.acquire(800)    # must wait for it to leave the window
        return time.monotonic() - t

    waited = run_async(run)
    assert 0.2 <= waited < 2.0


def test_token_budget_fails_fast_beyond_max_wait():
    from app.services.groq_client import LLMError, TokenBudget

    async def run():
        b = TokenBudget(1000)
        await b.acquire(900)
        t = time.monotonic()
        with pytest.raises(LLMError) as e:
            await b.acquire(900, max_wait=1.0)  # would need ~60 s
        return time.monotonic() - t, e.value

    took, err = run_async(run)
    assert took < 0.5 and err.code == "rate_limited" and err.provider_limited
