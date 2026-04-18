import os
import threading
import time

import uvicorn

from app.main import app as fastapi_app
from frontend import app as flask_app


def run_fastapi() -> None:
    host = os.getenv("FASTAPI_HOST", "127.0.0.1")
    port = int(os.getenv("FASTAPI_PORT", "8000"))
    uvicorn.run(fastapi_app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()

    # Give the API server a moment to bind before the UI starts proxying to it.
    time.sleep(1)

    flask_host = os.getenv("FLASK_HOST", "127.0.0.1")
    flask_port = int(os.getenv("FLASK_PORT", "5000"))
    flask_app.run(host=flask_host, port=flask_port, debug=False, use_reloader=False)
