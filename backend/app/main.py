from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "LawTalk backend running 🚀"}

@app.get("/health")
def health():
    return {"status": "ok"}