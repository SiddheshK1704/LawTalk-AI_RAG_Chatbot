from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
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


def retrieve_context(query: str, k: int = 3) -> str:
    database = load_db()
    docs = database.similarity_search(query, k=k)
    return "\n\n".join([doc.page_content for doc in docs])