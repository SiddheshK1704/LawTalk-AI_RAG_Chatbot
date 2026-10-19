"""Shared helpers for backend tests (kept out of conftest.py so imports stay unambiguous)."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX_BUILT = (ROOT / "backend" / "faiss_index_v2" / "index.faiss").exists() or (ROOT / "backend" / "faiss_index" / "index.faiss").exists()
needs_index = pytest.mark.skipif(not INDEX_BUILT, reason="FAISS index not built (python -m app.services.ingest)")
