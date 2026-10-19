"""Browser tests. Supabase and the LawTalk API are mocked at the network layer, so no
credentials, backend or LLM calls are needed. Requires: pip install playwright &&
python -m playwright install chromium."""
import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
playwright = pytest.importorskip("playwright.sync_api")

from _browser import FRONTEND  # noqa: E402


@pytest.fixture(scope="session")
def base_url():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(FRONTEND))
    handler.log_message = lambda *a, **k: None
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    httpd.shutdown()


@pytest.fixture(scope="session")
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


