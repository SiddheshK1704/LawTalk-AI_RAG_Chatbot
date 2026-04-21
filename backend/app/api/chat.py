from fastapi import APIRouter
from app.models.schemas import Query
from app.services.router import is_legal_query
from app.services.groq_client import get_llm_response
from app.services.rag import retrieve_context

router = APIRouter()

@router.post("/ask")
def ask(q: Query):
    query = q.query

    use_rag = is_legal_query(query)
    print("Mode:", "RAG" if use_rag else "LLM")

    context = ""
    if use_rag:
        context = retrieve_context(query)

        # 🔥 fallback if context is weak
        if not context or len(context.strip()) < 100:
            use_rag = False

    if use_rag:
        prompt = f"""
You are LawTalk, an Indian legal assistant.

INSTRUCTIONS:
- Use the context to answer the question
- If context is limited, still give a helpful answer using general knowledge
- Format response in clean HTML
- Use only these tags: <h2>, <p>, <ul>, <li>, <strong>
- Do NOT use markdown or code blocks

Context:
{context}

Question:
{query}

Answer:
"""
    else:
        prompt = f"""
You are a helpful assistant.

INSTRUCTIONS:
- Respond naturally and helpfully
- Format response in clean HTML
- Use only these tags: <h2>, <p>, <ul>, <li>, <strong>
- Do NOT use markdown or code blocks

Question:
{query}

Answer:
"""

    answer = get_llm_response(prompt)

    # basic cleanup
    answer = answer.replace("```html", "").replace("```", "")

    return {
        "answer": answer,
        "mode": "RAG" if use_rag else "LLM"
    }