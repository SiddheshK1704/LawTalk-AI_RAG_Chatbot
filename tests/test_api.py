"""API contract in both modes, with the LLM and auth replaced by fakes (no network)."""
import json

import pytest
from _support import needs_index
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch, rag):
    from app.api import chat
    from app.core import auth

    async def fake_user(request):
        if not request.headers.get("authorization"):
            raise auth.AuthError("unauthorized", "Please sign in to use LawTalk.", 401)
        return "user-1"

    calls = []

    async def fake_complete(messages, timer=None, max_tokens=None):
        calls.append(messages)
        return "Murder is punishable with death or imprisonment for life [1]. See also [9]." if "SOURCES" in messages[-1]["content"] else "Paris is the capital of France."

    async def fake_stream(messages, timer=None, max_tokens=None):
        calls.append(messages)
        text = "Theft is punishable with up to three years [1][2]." if "SOURCES" in messages[-1]["content"] else "Here is a joke."
        for word in text.split(" "):
            yield word + " "

    monkeypatch.setattr(chat, "require_user", fake_user)
    monkeypatch.setattr(chat, "get_llm_response", fake_complete)
    monkeypatch.setattr(chat, "stream_llm_response", fake_stream)
    from app.main import app

    with TestClient(app) as c:
        c.calls = calls
        yield c


AUTH = {"Authorization": "Bearer test"}


def _sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@needs_index
def test_ask_requires_auth(client):
    assert client.post("/ask", json={"query": "What is the punishment for murder?"}).status_code == 401


@needs_index
def test_ask_legal_query_is_rag_with_valid_citations(client):
    r = client.post("/ask", json={"query": "What is the punishment for murder under the IPC?"}, headers=AUTH)
    body = r.json()
    assert r.status_code == 200
    assert body["mode"] == "RAG"
    assert len(body["sources"]) == 5 and all(s["text"] for s in body["sources"])
    assert "[9]" not in body["answer"] and body["citations"] == [1]  # citation to a non-existent source removed
    assert "SOURCES" in client.calls[-1][-1]["content"]


@needs_index
def test_ask_general_query_is_normal_mode_without_sources(client):
    r = client.post("/ask", json={"query": "What is the capital of France?"}, headers=AUTH)
    body = r.json()
    assert body["mode"] == "LLM" and body["sources"] == [] and body["citations"] == []
    assert "SOURCES" not in client.calls[-1][-1]["content"]  # no retrieval in normal mode


@needs_index
def test_stream_legal_sends_sources_first(client):
    r = client.post("/ask/stream", json={"query": "What is the punishment for theft?"}, headers=AUTH)
    events = _sse(r.text)
    assert events[0][0] == "sources" and events[0][1]["mode"] == "RAG" and len(events[0][1]["sources"]) == 5
    assert any(e == "token" for e, _ in events)
    done = events[-1]
    assert done[0] == "done" and done[1]["mode"] == "RAG" and done[1]["citations"] == [1, 2]


@needs_index
def test_stream_general_has_no_sources(client):
    r = client.post("/ask/stream", json={"query": "Tell me a joke"}, headers=AUTH)
    events = _sse(r.text)
    assert events[0] == ("sources", {"mode": "LLM", "sources": []})
    assert events[-1][0] == "done" and events[-1][1]["mode"] == "LLM" and events[-1][1]["sources"] == []


def test_blank_query_rejected():
    from app.models.schemas import Query

    with pytest.raises(Exception):
        Query(query="   ")
