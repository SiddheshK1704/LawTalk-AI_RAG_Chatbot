"""Browser-test helpers: page factory with mocked Supabase, SSE builders."""
import json
import time
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
REF = "cqbmnahmfcrqgurgevhw"
SUPA = f"https://{REF}.supabase.co"
USER = {"id": "u-1", "email": "reviewer@example.com", "aud": "authenticated", "role": "authenticated", "identities": [{"id": "1"}]}
SESSION = {"access_token": "test-token", "refresh_token": "r", "token_type": "bearer", "expires_in": 3600,
           "expires_at": int(time.time()) + 36000, "user": USER}



def new_page(browser, *, width=1440, height=900, theme="dark", session=False, reduced=False, touch=False):
    ctx = browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce" if reduced else "no-preference",
                              has_touch=touch, is_mobile=touch)
    init = f"localStorage.setItem('lawtalk-theme', '{theme}');"
    if session:
        init += f"localStorage.setItem('sb-{REF}-auth-token', {json.dumps(json.dumps(SESSION))});"
    ctx.add_init_script(init)
    page = ctx.new_page()
    page.errors = []
    page.on("pageerror", lambda e: page.errors.append(str(e)))
    page.on("console", lambda m: page.errors.append(m.text) if m.type == "error" else None)
    page.route(f"{SUPA}/auth/v1/user**", lambda r, q: r.fulfill(json=USER))
    return ctx, page


def sse(mode: str, sources: list, answer: str) -> str:
    return (f"event: sources\ndata: {json.dumps({'mode': mode, 'sources': sources})}\n\n"
            f"event: token\ndata: {json.dumps({'text': answer})}\n\n"
            f"event: done\ndata: {json.dumps({'answer': answer, 'mode': mode, 'citations': [1] if sources else [], 'sources': sources})}\n\n")


def source(i: int, title: str, text: str, page: int = 72, section: str | None = "302") -> dict:
    return {"id": i, "chunk_id": f"c-{title[:3]}-{i}", "title": title, "file": "IPC_pdf.pdf", "page": page, "page_end": None,
            "section": section, "section_title": "Punishment for murder" if section else None, "section_kind": "Section" if section else None,
            "note": None, "text": f"{title}\n{text}", "score": 0.7, "cited": i == 1}
