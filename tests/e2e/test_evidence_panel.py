"""Evidence panel: opens only for legal (RAG) answers; never shows stale evidence."""
import json

from _browser import SUPA, new_page, source, sse

LEGAL_Q = "What is the punishment for murder under the IPC?"
LEGAL_Q2 = "What is the punishment for theft?"
GENERAL_Q = "Tell me a joke"
MURDER = [source(1, "Indian Penal Code", "302. Whoever commits murder shall be punished with death."),
          source(2, "Indian Penal Code", "303. Punishment for murder by life-convict.", section="303")]
THEFT = [source(1, "Indian Penal Code", "379. Whoever commits theft shall be punished...", page=89, section="379")]

CHATS = [{"id": "chat-rag", "user_id": "u-1", "title": "Murder punishment", "created_at": "2026-10-19T10:00:00Z"},
         {"id": "chat-gen", "user_id": "u-1", "title": "A joke", "created_at": "2026-10-18T10:00:00Z"}]
MESSAGES = {
    "chat-rag": [{"id": "m1", "chat_id": "chat-rag", "role": "user", "content": LEGAL_Q, "created_at": "2026-10-19T10:00:01Z"},
                 {"id": "m2", "chat_id": "chat-rag", "role": "assistant", "content": "Death or life imprisonment [1].",
                  "sources": MURDER, "created_at": "2026-10-19T10:00:02Z"}],
    "chat-gen": [{"id": "m3", "chat_id": "chat-gen", "role": "user", "content": GENERAL_Q, "created_at": "2026-10-18T10:00:01Z"},
                 {"id": "m4", "chat_id": "chat-gen", "role": "assistant", "content": "Why did the chicken...", "sources": [],
                  "created_at": "2026-10-18T10:00:02Z"}],
}


def setup(page, delay_theft=False):
    def supa(route, request):
        if "/rest/v1/chats" in request.url:
            if request.method == "GET":
                return route.fulfill(json=CHATS)
            return route.fulfill(status=201, json={"id": "chat-new", "user_id": "u-1", "title": "New", "created_at": "2026-10-19T12:00:00Z"})
        if "/rest/v1/messages" in request.url and request.method == "GET":
            cid = "chat-rag" if "chat-rag" in request.url else "chat-gen"
            return route.fulfill(json=MESSAGES[cid])
        return route.fulfill(status=201, json={"id": "m-x"})

    def api(route, request):
        q = json.loads(request.post_data)["query"]
        body = sse("RAG", MURDER, "Death or life imprisonment [1].") if q == LEGAL_Q else \
            sse("RAG", THEFT, "Up to three years [1].") if q == LEGAL_Q2 else sse("LLM", [], "Here is a joke.")
        route.fulfill(status=200, headers={"content-type": "text/event-stream"}, body=body)

    page.route(f"{SUPA}/rest/**", supa)
    page.route("**/ask/stream", api)


def ask(page, q):
    n = page.locator(".msg-ai .msg-actions").count()
    page.fill("#chatInput", q)
    page.keyboard.press("Enter")
    page.wait_for_function(f"document.querySelectorAll('.msg-ai .msg-actions').length > {n}", timeout=10000)
    page.wait_for_timeout(400)


def panel_open(page):
    return not page.evaluate("document.getElementById('app').classList.contains('evidence-closed')")


def test_general_query_keeps_panel_closed(browser, base_url):
    ctx, page = new_page(browser, session=True)
    setup(page)
    page.goto(base_url + "chat.html"); page.wait_for_selector(".chat-item")
    ask(page, GENERAL_Q)
    assert not panel_open(page)
    assert page.locator("#evidenceBody .source-card").count() == 0
    assert page.locator("#toggleEvidence").is_hidden()
    assert page.locator(".msg-ai .cite").count() == 0
    assert "general" in page.locator(".msg-ai .msg-role").last.inner_text().lower()
    assert not page.errors, page.errors
    ctx.close()


def test_legal_query_opens_panel_with_its_sources(browser, base_url):
    ctx, page = new_page(browser, session=True)
    setup(page)
    page.goto(base_url + "chat.html"); page.wait_for_selector(".chat-item")
    ask(page, LEGAL_Q)
    assert panel_open(page)
    assert page.locator("#evidenceBody .source-card").count() == 2
    assert "Section 302" in page.locator("#src-1").inner_text() and "p. 72" in page.locator("#src-1").inner_text()
    assert "legal rag" in page.locator(".msg-ai .msg-role").last.inner_text().lower()
    page.locator(".msg-ai .cite").first.click()
    assert page.locator("#src-1.highlight").count() == 1
    ctx.close()


def test_legal_then_general_clears_and_hides_evidence(browser, base_url):
    ctx, page = new_page(browser, session=True)
    setup(page)
    page.goto(base_url + "chat.html"); page.wait_for_selector(".chat-item")
    ask(page, LEGAL_Q)
    assert panel_open(page)
    ask(page, GENERAL_Q)
    assert not panel_open(page)
    assert page.locator("#evidenceBody .source-card").count() == 0
    assert page.locator("#toggleEvidence").is_hidden()
    ask(page, LEGAL_Q2)  # and back to legal: only the new answer's evidence
    assert panel_open(page)
    assert page.locator("#evidenceBody .source-card").count() == 1
    assert "379" in page.locator("#evidenceBody").inner_text() and "302" not in page.locator("#evidenceBody").inner_text()
    ctx.close()


def test_no_stale_evidence_while_next_answer_is_pending(browser, base_url):
    ctx, page = new_page(browser, session=True)
    setup(page)
    page.goto(base_url + "chat.html"); page.wait_for_selector(".chat-item")
    ask(page, LEGAL_Q)
    # Hold the next response open so the in-between state can be inspected.
    page.evaluate("""() => { const orig = window.fetch; window.__release = null;
      window.fetch = (url, opts) => String(url).includes('/ask/stream')
        ? new Promise(res => { window.__release = () => res(orig(url, opts)); }) : orig(url, opts); }""")
    page.fill("#chatInput", LEGAL_Q2)
    page.keyboard.press("Enter")
    page.wait_for_function("typeof window.__release === 'function'")
    body = page.locator("#evidenceBody").inner_text()
    assert "302" not in body and "Retrieving passages" in body
    page.evaluate("window.__release()")
    page.wait_for_function("document.querySelectorAll('.msg-ai .msg-actions').length >= 2", timeout=10000)
    assert "379" in page.locator("#evidenceBody").inner_text()
    ctx.close()


def test_switching_conversations_shows_only_their_evidence(browser, base_url):
    ctx, page = new_page(browser, session=True)
    setup(page)
    page.goto(base_url + "chat.html"); page.wait_for_selector(".chat-item")
    page.locator(".chat-open", has_text="Murder punishment").click()
    page.wait_for_selector(".msg-ai .cite")
    page.wait_for_timeout(300)
    assert panel_open(page) and page.locator("#evidenceBody .source-card").count() == 2
    page.locator(".chat-open", has_text="A joke").click()
    page.wait_for_selector(".msg-ai .prose")
    page.wait_for_timeout(300)
    assert not panel_open(page)
    assert page.locator("#evidenceBody .source-card").count() == 0 and page.locator("#toggleEvidence").is_hidden()
    page.locator(".chat-open", has_text="Murder punishment").click()
    page.wait_for_selector(".msg-ai .cite")
    page.wait_for_timeout(300)
    assert page.locator("#evidenceBody .source-card").count() == 2
    page.locator("#newChatBtn").click()
    page.wait_for_timeout(300)
    assert not panel_open(page) and page.locator("#evidenceBody .source-card").count() == 0
    ctx.close()


def test_mobile_drawer_only_for_legal(browser, base_url):
    ctx, page = new_page(browser, width=390, height=844, session=True, touch=True)
    setup(page)
    page.goto(base_url + "chat.html"); page.wait_for_timeout(800)
    ask(page, GENERAL_Q)
    assert page.locator("#toggleEvidence").is_hidden()
    ask(page, LEGAL_Q)
    assert page.locator("#toggleEvidence").is_visible()
    page.locator("#toggleEvidence").tap(); page.wait_for_timeout(400)
    assert page.evaluate("document.getElementById('app').classList.contains('evidence-open-mobile')")
    assert page.locator("#evidenceBody .source-card").count() == 2
    ctx.close()


def test_evidence_toggle_hidden_on_a_fresh_conversation(browser, base_url):
    ctx, page = new_page(browser, session=True)
    setup(page)
    page.goto(base_url + "chat.html"); page.wait_for_selector(".chat-item")
    assert page.locator("#toggleEvidence").is_hidden() and not panel_open(page)
    ctx.close()
