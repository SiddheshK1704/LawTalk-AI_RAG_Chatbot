import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
# gpt-oss "thinks" before answering; "low" cuts time-to-first-token. "" disables.
GROQ_REASONING_EFFORT = os.getenv("GROQ_REASONING_EFFORT", "low")
GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "1024"))
GROQ_TIMEOUT_S = float(os.getenv("GROQ_TIMEOUT_S", "30"))
GROQ_MAX_RETRIES = int(os.getenv("GROQ_MAX_RETRIES", "2"))
LLM_MAX_CONCURRENCY = int(os.getenv("LLM_MAX_CONCURRENCY", "8"))
# Client-side tokens-per-minute pacing (Groq free tier allows 8,000/min per model). 0 disables.
GROQ_TPM_BUDGET = int(os.getenv("GROQ_TPM_BUDGET", "7000"))
# Longest a request may wait for that budget before failing fast with "busy, retry in N s".
GROQ_MAX_QUEUE_S = float(os.getenv("GROQ_MAX_QUEUE_S", "20"))

TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))
METRICS_SUMMARY_EVERY = int(os.getenv("METRICS_SUMMARY_EVERY", "20"))
