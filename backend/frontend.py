import os

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder=None)

FASTAPI_HOST = os.getenv("FASTAPI_HOST", "127.0.0.1")
FASTAPI_PORT = os.getenv("FASTAPI_PORT", "8000")
FASTAPI_BASE_URL = os.getenv(
    "FASTAPI_BASE_URL", f"http://{FASTAPI_HOST}:{FASTAPI_PORT}"
).rstrip("/")


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/assets/<path:filename>")
def template_asset(filename: str):
    return send_from_directory(app.template_folder, filename)


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    mode = (payload.get("mode") or "rag").strip().lower()

    if not message:
        return jsonify({"error": "Message is required."}), 400
    if mode not in {"rag", "groq"}:
        return jsonify({"error": "Invalid chat mode."}), 400

    try:
        response = requests.post(
            f"{FASTAPI_BASE_URL}/ask",
            json={"query": message, "mode": mode},
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException:
        return (
            jsonify(
                {
                    "error": "Unable to reach the backend service. Make sure FastAPI is running."
                }
            ),
            502,
        )

    data = response.json()
    return jsonify({"answer": data.get("answer", ""), "mode": data.get("mode", mode)})


if __name__ == "__main__":
    app.run(debug=False, port=5000, use_reloader=False)
