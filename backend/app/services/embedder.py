from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

DATA_PATH = os.path.join(BASE_DIR, "data", "legal_docs")
DB_PATH = os.path.join(BASE_DIR, "faiss_index")

def create_vector_db():
    documents = []

    if not os.path.exists(DATA_PATH):
        print("❌ DATA_PATH does not exist:", DATA_PATH)
        return

    print("✅ DATA_PATH:", DATA_PATH)
    print("📂 FILES:", os.listdir(DATA_PATH))

    for file in os.listdir(DATA_PATH):
        file_path = os.path.join(DATA_PATH, file)

        if file.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
            documents.extend(loader.load())

        elif file.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
                documents.append(Document(page_content=text))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )

    docs = splitter.split_documents(documents)

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    clean_docs = []
    for doc in docs:
        text = doc.page_content.strip()

        if len(text) < 50:
            continue

        if text.isdigit():
            continue

        if "EP-IL&GL" in text:
            continue

        clean_docs.append(doc)

    print(f"🧹 Clean docs: {len(clean_docs)} / {len(docs)}")

    db = FAISS.from_documents(clean_docs, embeddings)
    db.save_local(DB_PATH)

    print("🔥 FAISS index created!")

if __name__ == "__main__":
    create_vector_db()