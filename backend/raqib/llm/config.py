"""Local LLM settings (all overridable by environment variables)."""
from __future__ import annotations

import os

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
# Preferred models, in order: the non-thinking instruct build answers directly (the plain qwen3:4b tag is a
# thinking build whose reasoning leaks into the answer when thinking is disabled).
PREFERRED_MODELS = ["qwen3:4b-instruct", "qwen3:4b-instruct-2507-q4_K_M", "qwen3:4b"]
LLM_MODEL_ENV = os.environ.get("LLM_MODEL", "").strip()
TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "25"))
# First call loads the model into memory (slow on a CPU-only laptop).
COLD_TIMEOUT = float(os.environ.get("LLM_COLD_TIMEOUT", "120"))
# When Ollama was unreachable, probe it again after this many seconds (it may have been started after RAQIB).
RECHECK = float(os.environ.get("LLM_RECHECK", "10"))
MODE_ENV = os.environ.get("RAQIB_LLM", "").strip().lower()  # "ollama" | "off" | "" (auto)
OPTIONS = {"temperature": 0.2, "num_ctx": 4096, "num_predict": 350}
KEEP_ALIVE = "30m"
