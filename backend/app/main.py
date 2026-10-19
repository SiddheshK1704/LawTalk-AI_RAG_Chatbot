import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.core import auth
from app.core.metrics import logger, print_eval_banner, tracker
from app.services.rag import load_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    t0 = time.perf_counter()
    load_db()  # embedding model + FAISS index, once per worker
    await auth.start()
    logger.info("[STARTUP] model and index loaded in %.1fs", time.perf_counter() - t0)
    if not auth.configured():
        logger.warning("[STARTUP] SUPABASE_URL / SUPABASE_KEY not set: /ask requests will be rejected (503)")
    print_eval_banner()
    yield
    tracker.print_summary("shutdown")
    await auth.stop()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "LawTalk backend running"}


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(chat_router)
