import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval"))
os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")

import pytest  # noqa: E402

from _support import INDEX_BUILT  # noqa: E402


@pytest.fixture(scope="session")
def rag():
    if not INDEX_BUILT:
        pytest.skip("FAISS index not built")
    from app.services import rag as rag_module

    rag_module.load_db()
    return rag_module
