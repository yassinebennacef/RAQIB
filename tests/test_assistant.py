"""Assistant RAQIB: retrieval, grounding, guards and fallbacks (no Ollama needed)."""
import json

import pytest
from fastapi.testclient import TestClient

from raqib.llm import assistant as A
from raqib.llm import client


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "CACHE_DIR", tmp_path / "assistant_cache")


def test_kb_has_sections():
    kb = A.load_kb()
    assert len(kb) >= 35 and all(s["text"] and s["page"] for s in kb)


@pytest.mark.parametrize("q,key", [
    ("Comment RAQIB choisit les contrôles ?", "allocation"),
    ("Que signifie précision à 5 % ?", "precision5"),
    ("D'où viennent les données ?", "data"),
    ("What does models disagree mean?", "disagreement"),
    ("ماذا يعني اختلاف النموذجين؟", "disagreement"),
    ("ما هي المسارات الثلاثة؟", "lanes"),
])
def test_retrieval(q, key):
    assert A.retrieve(q, 1)[0][0]["key"] == key


def test_out_of_scope_refused_without_llm(monkeypatch):
    monkeypatch.setattr(client, "available", lambda: False)
    r = A.answer([{"role": "user", "content": "Quelle est la capitale de l'Australie ?"}], "fr", "/")
    assert r["source"] == "faq" and r.get("out_of_scope") and "ne trouve pas" in r["answer"]


def test_declaration_context_does_not_answer_unrelated_questions(monkeypatch):
    monkeypatch.setattr(client, "available", lambda: False)
    facts = {"declaration_id": "54794554", "fraud_risk_percent": 74.1}
    r = A.answer([{"role": "user", "content": "Quelle est la capitale de l'Australie ?"}], "fr",
                 "/declaration/54794554", facts)
    assert r["source"] == "faq" and r["out_of_scope"] and not r["guard_passed"]


def test_faq_fallback_and_filter_request(monkeypatch):
    monkeypatch.setattr(client, "available", lambda: False)
    r = A.answer([{"role": "user", "content": "Que fait l'exploration ?"}], "fr", "/")
    assert r["source"] == "faq" and "hasard" in r["answer"]
    parsed = {"understood": True, "explanation": "lane RED · origin CN", "filter": {"lane": ["RED"]}, "source": "rules"}
    r = A.answer([{"role": "user", "content": "montre-moi les rouges de Chine"}], "fr", "/", nlq_parse=lambda q: parsed)
    assert r["kind"] == "filter" and r["filter"]["lane"] == ["RED"]


def test_guard_rejects_invented_number(monkeypatch):
    monkeypatch.setattr(client, "available", lambda: True)
    monkeypatch.setattr(client, "chat", lambda *a, **k: (json.dumps({"answer": "RAQIB inspecte 37 % des déclarations "
                                                                                "chaque jour selon la base.", "page": "About"}), 10))
    r = A.answer([{"role": "user", "content": "Comment RAQIB choisit les contrôles ?"}], "fr", "/")
    assert r["source"] == "faq" and any("numbers" in p for p in r["rejected"])


def test_generic_arabic_refusal_retries_then_uses_grounded_facts(monkeypatch):
    monkeypatch.setattr(client, "available", lambda: True)
    answers = iter([
        json.dumps({"answer": "لا توجد معلومات كافية في السياق لتحديد السؤال المطروح.", "page": "About"}),
        json.dumps({"answer": "لا توجد معلومات كافية في السياق لتحديد السؤال المطروح.", "page": "About"}),
    ])
    monkeypatch.setattr(client, "chat", lambda *a, **k: (next(answers), 10))
    facts = {
        "declaration_id": "54794554",
        "lane": "RED (physical inspection)",
        "fraud_risk_percent": 74.1,
        "safety_risk_percent": 0.0,
        "current_rule_decision": "release",
        "risk_indicators": [],
    }
    r = A.answer([{"role": "user", "content": "ما قرار القاعدة الحالية لهذا التصريح؟"}], "ar",
                 "/declaration/54794554", facts)
    assert r["source"] == "faq" and r["guard_passed"] and r["dir"] == "rtl"
    assert "74.1" in r["answer"] and "المسار الأحمر" in r["answer"]
    assert r["attempts"] == 2


def test_why_red_starter_uses_instant_verified_faq(monkeypatch):
    monkeypatch.setattr(client, "available", lambda: True)
    monkeypatch.setattr(client, "chat", lambda *a, **k: pytest.fail("FAQ fast path must not wait for Ollama"))
    facts = {
        "declaration_id": "54794554",
        "lane": "RED (physical inspection)",
        "fraud_risk_percent": 74.1,
        "safety_risk_percent": 0.0,
        "current_rule_decision": "release",
        "risk_indicators": [],
    }
    for lang, q in (
        ("fr", "Pourquoi cette déclaration est ROUGE ?"),
        ("ar", "لماذا هذا التصريح في المسار الأحمر؟"),
    ):
        r = A.answer([{"role": "user", "content": q}], lang, "/declaration/54794554", facts)
        assert r["source"] == "faq" and r["guard_passed"] and r["latency_ms"] < 12000
        assert "74.1" in r["answer"]
        assert r["dir"] == ("rtl" if lang == "ar" else "ltr")


def test_grounded_answer_accepted(monkeypatch):
    monkeypatch.setattr(client, "available", lambda: True)
    monkeypatch.setattr(client, "chat", lambda *a, **k: (json.dumps({
        "answer": "Chaque jour, les alertes de sécurité publique passent d'abord, puis les risques de fraude les plus élevés, "
                  "et une petite part des inspections est tirée au hasard pour l'exploration.", "page": "Salle de contrôle"}), 10))
    r = A.answer([{"role": "user", "content": "Comment RAQIB choisit les contrôles ?"}], "fr", "/")
    assert r["source"] == "qwen3-4b" and r["guard_passed"] and r["citations"][0]["key"] == "allocation"


@pytest.fixture(scope="module")
def off_client(built):
    import os
    from raqib.llm import config as K
    os.environ["RAQIB_LLM"] = "off"
    K.MODE_ENV = "off"
    client._state["checked"] = False
    from raqib.api import app
    with TestClient(app) as c:
        yield c
    os.environ.pop("RAQIB_LLM", None)
    K.MODE_ENV = ""
    client._state["checked"] = False


def test_endpoint_with_llm_off(off_client):
    r = off_client.post("/api/assistant", json={"messages": [{"role": "user", "content": "Pourquoi cette déclaration est ROUGE ?"}],
                                                "lang": "fr", "page": "/declaration/54794554"}).json()
    assert r["source"] == "faq" and r["declaration_id"] == "54794554" and "règle actuelle" in r["answer"].lower()
    assert r["guard_passed"]
    r = off_client.post("/api/assistant", json={"messages": [{"role": "user", "content": "لماذا هذا التصريح في المسار الأحمر؟"}],
                                                "lang": "ar", "page": "/declaration/54794554"}).json()
    assert r["source"] == "faq" and r["guard_passed"] and r["dir"] == "rtl" and "المسار الأحمر" in r["answer"]
    r = off_client.post("/api/assistant", json={"messages": [{"role": "user", "content": "ما هو الاستكشاف؟"}], "lang": "ar"}).json()
    assert r["dir"] == "rtl" and r["answer"]
    r = off_client.post("/api/assistant", json={"messages": [{"role": "user", "content": "montre-moi les rouges de Chine au chapitre 85"}],
                                                "lang": "fr", "page": "/worklist"}).json()
    assert r.get("kind") == "filter" and r["filter"]["origin"] == ["CN"]
