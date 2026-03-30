from fastapi import APIRouter
from app.models.schemas import Query
from app.services.router import is_legal_query

router = APIRouter()

@router.post("/ask")
def ask(q: Query):
    query = q.query

    if is_legal_query(query):
        return {
            "mode": "RAG",
            "answer": f"[Legal Mode] Processing: {query}"
        }
    else:
        return {
            "mode": "NORMAL",
            "answer": f"[General Mode] {query}"
        }