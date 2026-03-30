from fastapi import FastAPI
from app.api.chat import router as chat_router

app = FastAPI()

@app.get("/")
def root():
    return {"message": "LawTalk backend running 🚀"}

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(chat_router)