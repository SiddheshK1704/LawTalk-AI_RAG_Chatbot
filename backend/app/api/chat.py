from fastapi import APIRouter
from app.models.schemas import Query
from app.services.router import is_legal_query
from app.services.groq_client import get_llm_response

router = APIRouter()

@router.post("/ask")
def ask(q: Query):
    query = q.query

    if is_legal_query(query):
        prompt = f"You are a legal assistant. Answer this: {query}"
    else:
        prompt = query

    answer = get_llm_response(prompt)

    return {"answer": answer}