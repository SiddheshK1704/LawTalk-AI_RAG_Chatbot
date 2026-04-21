from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
ASSETS_DIR = FRONTEND_DIR / "assets"
JS_DIR = FRONTEND_DIR / "js"

if DIST_DIR.exists():
    app.mount("/dist", StaticFiles(directory=DIST_DIR), name="dist")
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
if JS_DIR.exists():
    app.mount("/js", StaticFiles(directory=JS_DIR), name="js")


@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/chat")
def chat_page():
    return FileResponse(FRONTEND_DIR / "chat.html")


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(chat_router)
