"""Print a Supabase access token for EVAL_AUTH_TOKEN.

Signs in with an existing LawTalk account (email + password, the same sign-in the app
uses) and prints the access token. Tokens expire after about an hour.

    set EVAL_EMAIL=you@example.com          (macOS/Linux: export ...)
    set EVAL_PASSWORD=...
    python eval/get_token.py
    set EVAL_AUTH_TOKEN=<printed token>

Credentials are read from the environment and never written to disk.
"""
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")


def main() -> None:
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    email, password = os.environ.get("EVAL_EMAIL"), os.environ.get("EVAL_PASSWORD")
    if not (url and key):
        sys.exit("SUPABASE_URL / SUPABASE_KEY must be set (backend/.env).")
    if not (email and password):
        sys.exit("Set EVAL_EMAIL and EVAL_PASSWORD for an existing LawTalk account.")
    r = httpx.post(f"{url.rstrip('/')}/auth/v1/token?grant_type=password",
                   headers={"apikey": key}, json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        msg = r.json().get("msg") or r.json().get("error_description") or r.text[:200]
        sys.exit(f"Sign-in failed ({r.status_code}): {msg}")
    print(r.json()["access_token"])


if __name__ == "__main__":
    main()
