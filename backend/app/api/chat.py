from fastapi import APIRouter
from app.models.schemas import Query
from app.services.groq_client import get_llm_response
from app.services.rag import retrieve_context

router = APIRouter()

@router.post("/ask")
def ask(q: Query):
    query = q.query
    mode = q.mode

    if mode == "rag":
        context = retrieve_context(query)

        prompt = f"""
You are a LawTalk. A highly accurate Indian legal assistant.

STRICT RULES:
- Answer ONLY using the context below
- Do NOT use prior knowledge
- If answer is not in context, say "I don't know"

Context:
{context}

Question:
{query}

Answer:
"""
    else:
        prompt = query

    answer = get_llm_response(prompt)

    return {"answer": answer, "mode": mode}
