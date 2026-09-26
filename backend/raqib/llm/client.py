"""Minimal Ollama client (HTTP, stdlib only) with status, warm-up and latency stats."""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request

from . import config as K


class LLMError(RuntimeError):
    pass


_state = {"model": None, "reachable": False, "warm": False, "latencies": [], "calls": 0, "errors": 0,
          "installed": [], "think_supported": True, "checked": False}
_lock = threading.Lock()


def _http(path: str, body: dict | None = None, timeout: float = 5.0) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(K.OLLAMA_URL + path, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def enabled() -> bool:
    return K.MODE_ENV != "off"


def refresh_status() -> dict:
    """Probe Ollama and pick the model (called at startup and by /api/llm/status)."""
    if not enabled():
        _state.update(reachable=False, checked=True)
        return status()
    try:
        tags = _http("/api/tags", timeout=2.0)
        installed = [m["name"] for m in tags.get("models", [])]
        model = K.LLM_MODEL_ENV or next((m for m in K.PREFERRED_MODELS if m in installed), None)
        _state.update(reachable=model is not None, installed=installed, model=model, checked=True)
    except (OSError, ValueError, urllib.error.URLError):
        _state.update(reachable=False, checked=True)
    return status()


def available() -> bool:
    if not _state["checked"]:
        refresh_status()
    return enabled() and _state["reachable"] and _state["model"] is not None


def status() -> dict:
    lat = _state["latencies"]
    return {"enabled": enabled(), "mode": "ollama" if (enabled() and _state["reachable"]) else "off",
            "model": _state["model"], "reachable": _state["reachable"], "warm": _state["warm"],
            "avg_latency_ms": round(sum(lat) / len(lat)) if lat else None, "calls": _state["calls"],
            "errors": _state["errors"], "installed_models": _state["installed"]}


THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def chat(system: str, user: str, *, schema: dict | None = None, temperature: float | None = None,
         num_predict: int | None = None, timeout: float | None = None) -> tuple[str, int]:
    """Return (content, latency_ms). Raises LLMError on any failure (caller falls back)."""
    if not available():
        raise LLMError("LLM not available")
    opts = dict(K.OPTIONS)
    if temperature is not None:
        opts["temperature"] = temperature
    if num_predict is not None:
        opts["num_predict"] = num_predict
    body = {"model": _state["model"], "stream": False, "options": opts, "keep_alive": K.KEEP_ALIVE,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if _state["think_supported"]:
        body["think"] = False
    else:
        body["messages"][1]["content"] = user + " /no_think"
    if schema is not None:
        body["format"] = schema
    t0 = time.time()
    try:
        out = _http("/api/chat", body, timeout=timeout or K.TIMEOUT)
    except urllib.error.HTTPError as exc:
        if exc.code == 400 and _state["think_supported"]:  # old Ollama rejecting "think"
            _state["think_supported"] = False
            return chat(system, user, schema=schema, temperature=temperature, num_predict=num_predict, timeout=timeout)
        _state["errors"] += 1
        raise LLMError(f"HTTP {exc.code}") from exc
    except (OSError, ValueError, urllib.error.URLError) as exc:
        _state["errors"] += 1
        raise LLMError(str(exc)) from exc
    ms = int((time.time() - t0) * 1000)
    with _lock:
        _state["calls"] += 1
        _state["latencies"] = (_state["latencies"] + [ms])[-50:]
    content = THINK_RE.sub("", out.get("message", {}).get("content", "")).strip()
    if not content:
        raise LLMError("empty answer")
    return content, ms


def warm_up() -> None:
    """Load the model on the GPU (non-blocking caller: run in a thread)."""
    if not available():
        return
    try:
        chat("You answer in one word.", "Say OK.", num_predict=5, timeout=120)
        _state["warm"] = True
    except LLMError:
        pass
