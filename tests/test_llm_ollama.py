"""Regression tests for the Ollama client against a fake local Ollama server (no network, no model needed).

Covers the failures seen on the demo laptop: a system/env HTTP proxy capturing 127.0.0.1, a model tag that is
not spelled exactly like the config, Ollama started after RAQIB, and fallbacks that must say why.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from raqib.llm import brief as LB
from raqib.llm import client
from raqib.llm import config as K
from raqib.llm.nlq import Vocab, parse

GOOD = ("Cette déclaration présente plusieurs indicateurs de risque. Le risque de fraude estimé est de 71,8 %. "
        "Le produit 731815 a été frauduleux dans 45 % de ses 1 200 déclarations passées, contre 22 % en moyenne. "
        "Le risque pour la sécurité est faible et la décision revient à l'agent.")
FACTS = {"declaration_id": "54794554", "fraud_risk_percent": 71.8, "safety_risk_percent": 0.4,
         "risk_indicators": ["raises risk: product 731815 was fraudulent in 45% of its 1,200 past declarations (average 22%)"]}
VOCAB = Vocab(origins={"CN", "JP"}, offices={"20": "Incheon"}, hs6={"851712"}, importers=set(),
              date_min="2021-04-01", date_max="2021-06-30")


class FakeOllama(BaseHTTPRequestHandler):
    models = ["qwen3:4b-instruct"]
    chats: list[dict] = []

    def log_message(self, *a):  # quiet
        pass

    def _send(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/tags":
            self._send(200, {"models": [{"name": m} for m in self.models]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.chats.append(req)
        if req["model"] not in self.models:
            self._send(404, {"error": f"model '{req['model']}' not found"})
        elif "Question:" in req["messages"][1]["content"]:
            self._send(200, {"message": {"content": json.dumps({"lane": ["RED"], "origin": ["CN"]})}})
        else:
            self._send(200, {"message": {"content": json.dumps({"brief": GOOD, "suggested_check": "vérifier la facture"})}})


@pytest.fixture
def ollama(monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(K, "OLLAMA_URL", f"http://127.0.0.1:{srv.server_address[1]}")
    monkeypatch.setattr(K, "MODE_ENV", "")
    monkeypatch.setattr(K, "LLM_MODEL_ENV", "")
    monkeypatch.setattr(FakeOllama, "models", ["qwen3:4b-instruct"])
    FakeOllama.chats = []
    saved = dict(client._state)
    client._state.update(model=None, reachable=False, warm=False, checked=False, checked_at=0.0, last_error=None,
                         think_supported=True, installed=[])
    yield srv
    srv.shutdown()
    client._state.clear()
    client._state.update(saved)


def test_local_ollama_ignores_http_proxy(ollama, monkeypatch):
    # A proxy that does not exist: before the fix urllib sent 127.0.0.1 to it and Ollama looked unreachable.
    for var in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HTTP_PROXY", "http://10.255.255.1:3128")
    monkeypatch.setenv("http_proxy", "http://10.255.255.1:3128")
    st = client.refresh_status()
    assert st["reachable"] and st["mode"] == "ollama" and st["model"] == "qwen3:4b-instruct"
    text, ms = client.chat("sys", "user")
    assert json.loads(text)["brief"] == GOOD and FakeOllama.chats[-1]["think"] is False


@pytest.mark.parametrize("installed,expected", [
    (["qwen3:4b-instruct"], "qwen3:4b-instruct"),
    (["qwen3:4b-instruct:latest"], "qwen3:4b-instruct:latest"),
    (["llama3:8b", "qwen3:4b-instruct-2507-q8_0"], "qwen3:4b-instruct-2507-q8_0"),
    (["qwen3:4b", "qwen3:4b-instruct-2507-q4_K_M"], "qwen3:4b-instruct-2507-q4_K_M"),
    (["qwen3:latest"], "qwen3:latest"),
    (["llama3:8b"], None),
])
def test_model_name_matching(installed, expected):
    assert client.pick_model(installed) == expected


def test_missing_model_is_explained(ollama, monkeypatch):
    monkeypatch.setattr(FakeOllama, "models", ["llama3:8b"])
    st = client.refresh_status()
    assert not st["reachable"] and "ollama pull" in st["last_error"] and "llama3:8b" in st["last_error"]


def test_ollama_started_after_raqib_is_picked_up(ollama, monkeypatch):
    monkeypatch.setattr(K, "RECHECK", 0.0)
    good_url = K.OLLAMA_URL
    monkeypatch.setattr(K, "OLLAMA_URL", "http://127.0.0.1:9")  # nothing listens here: Ollama "not started yet"
    assert client.available() is False and "not reachable" in client.status()["last_error"]
    monkeypatch.setattr(K, "OLLAMA_URL", good_url)  # Ollama now running: the next request must use it
    assert client.available() is True


def test_brief_uses_qwen_then_says_why_it_falls_back(ollama, monkeypatch, tmp_path):
    monkeypatch.setattr(LB, "CACHE_DIR", tmp_path)
    b = LB.brief("54794554", "fr", FACTS, "TEMPLATE", refresh=True)
    assert b["source"] == "qwen3-4b" and b["guard_passed"] and b["model"] == "qwen3:4b-instruct"
    ollama.shutdown()
    ollama.server_close()
    monkeypatch.setattr(K, "RECHECK", 0.0)
    b = LB.brief("54794554", "fr", FACTS, "TEMPLATE", refresh=True)
    assert b["source"] == "template" and b["llm_fallback"] == "unavailable" and b["llm_error"]


def test_nlq_free_phrasing_uses_qwen_and_reports_fallback(ollama, monkeypatch):
    r = parse("what should I look at first today", VOCAB)
    assert r["source"] == "qwen3-4b" and r["filter"]["lane"] == ["RED"] and r["llm_fallback"] is None
    monkeypatch.setattr(K, "OLLAMA_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(K, "RECHECK", 0.0)
    client._state.update(reachable=False, checked_at=0.0)
    r = parse("what should I look at first today", VOCAB)
    assert r["source"] == "rules" and r["llm_fallback"] == "unavailable" and r["warnings"]


def test_llm_off_is_not_reported_as_a_failure(ollama, monkeypatch, tmp_path):
    monkeypatch.setattr(K, "MODE_ENV", "off")
    monkeypatch.setattr(LB, "CACHE_DIR", tmp_path)
    b = LB.brief("54794554", "fr", FACTS, "TEMPLATE", refresh=True)
    assert b["source"] == "template" and b["llm_fallback"] is None and not FakeOllama.chats
