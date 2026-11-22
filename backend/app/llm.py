"""Optional local AI model (Ollama).

The app must work without it: every function here fails safely.
"""
import os
import time

import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

# Remember the result of the last ping for 30 seconds,
# so we don't ping Ollama on every question.
_CACHE_SECONDS = 30
_last_check = {"time": 0.0, "available": False}


def is_available() -> bool:
    """True if Ollama answers on /api/tags (result cached for 30s)."""
    now = time.time()
    if now - _last_check["time"] < _CACHE_SECONDS:
        return _last_check["available"]

    try:
        response = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        available = response.status_code == 200
    except httpx.HTTPError:
        available = False

    _last_check["time"] = now
    _last_check["available"] = available
    return available
