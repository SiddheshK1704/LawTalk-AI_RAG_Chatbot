from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DB_PATH = os.path.join(BASE_DIR, "faiss_index")

db = None

def load_db():
    global db
    if db is None:
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        db = FAISS.load_local(DB_PATH, embeddings, allow_dangerous_deserialization=True)
    return db


def retrieve_context(query: str, k: int = 5) -> str:
    database = load_db()
    docs = database.similarity_search(query, k=k)

    print("\n🔍 QUERY:", query)
    print("📄 DOCS RETRIEVED:", len(docs))

    for i, doc in enumerate(docs):
        print(f"\n--- DOC {i+1} ---")
        print(doc.page_content[:300])

    return "\n\n".join([doc.page_content for doc in docs])