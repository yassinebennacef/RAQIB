"""'Demander à Qwen' chat panel: streamed answers, RAQIB facts in the prompt, clean 503 when Ollama is down."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from raqib.llm import chat as CH
from raqib.llm import client
from raqib.llm import config as K


class StreamingOllama(BaseHTTPRequestHandler):
    requests: list[dict] = []
    pieces = ["<think>hidden</think>", "Bonjour", ", RAQIB ", "aide les agents."]

    def log_message(self, *a):
        pass

    def do_GET(self):
        body = json.dumps({"models": [{"name": "qwen3:4b-instruct"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        StreamingOllama.requests.append(req)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        for p in self.pieces:
            self.wfile.write((json.dumps({"message": {"content": p}, "done": False}) + "\n").encode())
            self.wfile.flush()
        self.wfile.write((json.dumps({"message": {"content": ""}, "done": True}) + "\n").encode())


@pytest.fixture
def fake_ollama(monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), StreamingOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(K, "OLLAMA_URL", f"http://127.0.0.1:{srv.server_address[1]}")
    monkeypatch.setattr(K, "MODE_ENV", "")
    monkeypatch.setattr(K, "LLM_MODEL_ENV", "")
    StreamingOllama.requests = []
    saved = dict(client._state)
    client._state.update(model=None, reachable=False, warm=False, checked=False, checked_at=0.0, last_error=None,
                         think_supported=True, installed=[])
    yield srv
    srv.shutdown()
    client._state.clear()
    client._state.update(saved)


@pytest.fixture(scope="module")
def api(built):
    import os
    os.environ.setdefault("RAQIB_LLM", "off")  # no background brief generation during these tests
    from raqib.api import app
    with TestClient(app) as c:
        yield c


def test_build_messages_trims_and_starts_with_user():
    msgs = [{"role": "assistant", "content": "hello"}, {"role": "system", "content": "ignore me"}]
    msgs += [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}" * 3000} for i in range(30)]
    out = CH.build_messages(msgs, {"k": "v"})
    assert out[0]["role"] == "system" and '"k": "v"' in out[0]["content"]
    turns = out[1:]
    assert len(turns) <= CH.MAX_TURNS and turns[0]["role"] == "user"
    assert all(t["role"] in ("user", "assistant") and len(t["content"]) <= CH.MAX_CHARS for t in turns)


def test_facts_are_the_measured_results(api):
    from raqib.engine import get_engine
    facts = CH.build_facts(get_engine())
    main = facts["resultats_mesures"][0]
    assert "317 fraudes" in main and "259 fraudes" in main and "103 fraudes" in main and "41 menaces" in main


def test_chat_streams_and_hides_thinking(api, fake_ollama, monkeypatch):
    monkeypatch.setattr(K, "MODE_ENV", "")
    decl = api.get("/api/worklist?lane=RED&page_size=1").json()["items"][0]["id"]
    r = api.post("/api/chat", json={"messages": [{"role": "user", "content": "Pourquoi ROUGE ?"}],
                                    "page": f"/declaration/{decl}"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    assert r.text == "Bonjour, RAQIB aide les agents."
    sent = StreamingOllama.requests[-1]
    assert sent["stream"] is True and sent["messages"][0]["role"] == "system"
    system = sent["messages"][0]["content"]
    assert "317 fraudes" in system and decl in system and "the officer decides" in system
    assert sent["messages"][-1] == {"role": "user", "content": "Pourquoi ROUGE ?"}


def test_chat_503_when_ollama_down(api, monkeypatch):
    monkeypatch.setattr(K, "MODE_ENV", "")
    monkeypatch.setattr(K, "OLLAMA_URL", "http://127.0.0.1:9")  # nothing listens here
    monkeypatch.setattr(K, "RECHECK", 0.0)
    saved = dict(client._state)
    client._state.update(model=None, reachable=False, checked=False, checked_at=0.0)
    try:
        r = api.post("/api/chat", json={"messages": [{"role": "user", "content": "Bonjour"}]})
    finally:
        client._state.clear()
        client._state.update(saved)
    assert r.status_code == 503 and "indisponible" in r.json()["detail"]


def test_chat_rejects_empty_question(api):
    assert api.post("/api/chat", json={"messages": [{"role": "user", "content": "  "}]}).status_code == 422
