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
          "installed": [], "think_supported": True, "checked": False, "checked_at": 0.0, "last_error": None}
_lock = threading.Lock()
# Interactive calls (an officer clicked) take priority over the background brief pre-generation, which would
# otherwise hold Ollama's single slot for minutes after start-up and push clicks past the timeout.
_interactive = 0
_ilock = threading.Lock()
_warming = threading.Event()

# Ollama is always local: never route it through an HTTP proxy (the Windows system proxy or HTTP_PROXY would
# otherwise capture 127.0.0.1:11434 and the LLM would look unreachable).
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _http(path: str, body: dict | None = None, timeout: float = 5.0) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(K.OLLAMA_URL + path, data=data, headers={"Content-Type": "application/json"},
                                 method="POST" if body is not None else "GET")
    with _opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def enabled() -> bool:
    return K.MODE_ENV != "off"


def pick_model(installed: list[str]) -> str | None:
    """The configured model if installed, else the best Qwen3 build present (names are matched with or without
    ':latest' and by prefix, so 'qwen3:4b-instruct-2507-q8_0' or 'qwen3:latest' are found too)."""
    def norm(n: str) -> str:
        return n[:-len(":latest")] if n.endswith(":latest") else n
    by_norm = {norm(n): n for n in installed}
    wanted = [K.LLM_MODEL_ENV] if K.LLM_MODEL_ENV else []
    for w in wanted + K.PREFERRED_MODELS:
        if norm(w) in by_norm:
            return by_norm[norm(w)]
    for prefix in ("qwen3:4b-instruct", "qwen3:4b", "qwen3"):
        hits = sorted(n for n in installed if norm(n).startswith(prefix))
        if hits:
            return hits[0]
    return None


def refresh_status() -> dict:
    """Probe Ollama and pick the model (startup, /api/llm/status, and again before use when it was down)."""
    if not enabled():
        _state.update(reachable=False, checked=True, checked_at=time.time(), last_error="RAQIB_LLM=off")
        return status()
    try:
        tags = _http("/api/tags", timeout=2.0)
        installed = [m["name"] for m in tags.get("models", [])]
        model = pick_model(installed)
        err = None if model else (f"no Qwen3 model installed (run: ollama pull {K.PREFERRED_MODELS[1]}); "
                                  f"installed: {', '.join(installed) or 'none'}")
        if model != _state["model"]:
            _state["warm"] = False
        _state.update(reachable=model is not None, installed=installed, model=model, last_error=err)
        if model and not _state["warm"] and not _warming.is_set():  # Ollama came up (or model changed): load it now
            _warming.set()
            threading.Thread(target=warm_up, daemon=True).start()
    except (OSError, ValueError, urllib.error.URLError) as exc:
        _state.update(reachable=False, warm=False, last_error=f"Ollama not reachable at {K.OLLAMA_URL} ({exc})")
    _state.update(checked=True, checked_at=time.time())
    return status()


def available() -> bool:
    # Re-probe when unknown, or when it was down more than RECHECK seconds ago (Ollama started after RAQIB).
    if not _state["checked"] or (not _state["reachable"] and time.time() - _state["checked_at"] >= K.RECHECK):
        refresh_status()
    return enabled() and _state["reachable"] and _state["model"] is not None


def status() -> dict:
    lat = _state["latencies"]
    return {"enabled": enabled(), "mode": "ollama" if (enabled() and _state["reachable"]) else "off",
            "model": _state["model"], "reachable": _state["reachable"], "warm": _state["warm"],
            "avg_latency_ms": round(sum(lat) / len(lat)) if lat else None, "calls": _state["calls"],
            "errors": _state["errors"], "installed_models": _state["installed"], "last_error": _state["last_error"],
            "url": K.OLLAMA_URL}


THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def _fail(msg: str) -> LLMError:
    _state["errors"] += 1
    _state["last_error"] = msg
    return LLMError(msg)


def chat(system: str, user: str, *, schema: dict | None = None, temperature: float | None = None,
         num_predict: int | None = None, timeout: float | None = None, background: bool = False) -> tuple[str, int]:
    """Return (content, latency_ms). Raises LLMError on any failure (caller falls back)."""
    global _interactive
    if not available():
        raise LLMError(_state["last_error"] or "LLM not available")
    if background:
        # Yield to officers: wait while an interactive call is running (bounded, then go anyway).
        t_wait = time.time()
        while _interactive and time.time() - t_wait < 120:
            time.sleep(0.2)
    else:
        with _ilock:
            _interactive += 1
    try:
        return _chat(system, user, schema=schema, temperature=temperature, num_predict=num_predict, timeout=timeout)
    finally:
        if not background:
            with _ilock:
                _interactive -= 1


def _chat(system: str, user: str, *, schema, temperature, num_predict, timeout) -> tuple[str, int]:
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
    # The first call loads the model into memory (tens of seconds on a CPU laptop): allow for it.
    timeout = timeout or (K.TIMEOUT if _state["warm"] else max(K.TIMEOUT, K.COLD_TIMEOUT))
    t0 = time.time()
    try:
        out = _http("/api/chat", body, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except OSError:
            pass
        if exc.code == 400 and _state["think_supported"] and "think" in detail.lower():  # old Ollama rejecting "think"
            _state["think_supported"] = False
            return _chat(system, user, schema=schema, temperature=temperature, num_predict=num_predict, timeout=timeout)
        if exc.code == 404:  # model removed or renamed since the last probe
            _state.update(reachable=False, checked_at=time.time())
        raise _fail(f"Ollama HTTP {exc.code} for model {_state['model']}: {detail or exc.reason}") from exc
    except (OSError, ValueError, urllib.error.URLError) as exc:
        if isinstance(exc, TimeoutError) or "timed out" in str(exc):
            raise _fail(f"Ollama timed out after {timeout:.0f} s (model {_state['model']})") from exc
        _state.update(reachable=False, checked_at=time.time())
        raise _fail(f"Ollama not reachable at {K.OLLAMA_URL} ({exc})") from exc
    ms = int((time.time() - t0) * 1000)
    with _lock:
        _state["calls"] += 1
        _state["latencies"] = (_state["latencies"] + [ms])[-50:]
        _state["warm"] = True
        _state["last_error"] = None
    content = THINK_RE.sub("", out.get("message", {}).get("content", "")).strip()
    if not content:
        raise _fail("Ollama returned an empty answer")
    return content, ms


def stream_chat(messages: list[dict], *, temperature: float | None = None, num_predict: int | None = None,
                timeout: float | None = None):
    """Yield the answer piece by piece (Ollama streaming). Raises LLMError before the first piece on failure."""
    global _interactive
    if not available():
        raise LLMError(_state["last_error"] or "LLM not available")
    opts = dict(K.OPTIONS)
    if temperature is not None:
        opts["temperature"] = temperature
    if num_predict is not None:
        opts["num_predict"] = num_predict
    body = {"model": _state["model"], "stream": True, "options": opts, "keep_alive": K.KEEP_ALIVE,
            "messages": messages}
    if _state["think_supported"]:
        body["think"] = False
    timeout = timeout or (K.TIMEOUT if _state["warm"] else max(K.TIMEOUT, K.COLD_TIMEOUT))
    req = urllib.request.Request(K.OLLAMA_URL + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with _ilock:
        _interactive += 1
    t0 = time.time()
    try:
        try:
            resp = _opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                _state.update(reachable=False, checked_at=time.time())
            raise _fail(f"Ollama HTTP {exc.code} for model {_state['model']}") from exc
        except (OSError, urllib.error.URLError) as exc:
            if not (isinstance(exc, TimeoutError) or "timed out" in str(exc)):
                _state.update(reachable=False, checked_at=time.time())
            raise _fail(f"Ollama not reachable at {K.OLLAMA_URL} ({exc})") from exc
        in_think = False
        with resp:
            for line in resp:
                if not line.strip():
                    continue
                obj = json.loads(line.decode("utf-8"))
                buf, piece = obj.get("message", {}).get("content", ""), ""
                # a thinking build may still emit <think>...</think>: never show it
                while buf:
                    if in_think:
                        in_think = "</think>" not in buf
                        buf = "" if in_think else buf.split("</think>", 1)[1]
                    elif "<think>" in buf:
                        head, buf = buf.split("<think>", 1)
                        piece, in_think = piece + head, True
                    else:
                        piece, buf = piece + buf, ""
                if piece:
                    yield piece
                if obj.get("done"):
                    break
        ms = int((time.time() - t0) * 1000)
        with _lock:
            _state["calls"] += 1
            _state["latencies"] = (_state["latencies"] + [ms])[-50:]
            _state["warm"] = True
            _state["last_error"] = None
    finally:
        with _ilock:
            _interactive -= 1


def warm_up() -> None:
    """Load the model into memory (non-blocking caller: run in a thread)."""
    try:
        if available():
            chat("You answer in one word.", "Say OK.", num_predict=5, timeout=K.COLD_TIMEOUT, background=True)
            _state["warm"] = True
    except LLMError:
        pass
    finally:
        _warming.clear()
