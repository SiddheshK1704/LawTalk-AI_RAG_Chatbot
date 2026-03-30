from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

# Path to your FAISS index
DB_PATH = "backend/faiss_index"

# 🔥 Load once (important for performance)
embeddings = HuggingFaceEmbeddings()
db = None


def load_db():
    global db
    if db is None:
        db = FAISS.load_local(DB_PATH, embeddings, allow_dangerous_deserialization=True)
    return db


def retrieve_context(query: str, k: int = 3) -> str:
    """
    Retrieves top-k relevant chunks from FAISS
    """

    database = load_db()

    docs = database.similarity_search(query, k=k)

    # Extract text
    context = "\n\n".join([doc.page_content for doc in docs])

    return context