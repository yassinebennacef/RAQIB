"""Local LLM layer: guards, validation, fallbacks and endpoints (no Ollama needed: the HTTP call is mocked)."""
import json

import pytest
from fastapi.testclient import TestClient

from raqib.llm import brief as LB
from raqib.llm import client
from raqib.llm.guard import banned_claims, unmatched_numbers
from raqib.llm.nlq import Vocab, parse, rules_parse, validate

FACTS = {"declaration_id": "54794554", "fraud_risk_percent": 71.8, "safety_risk_percent": 0.4,
         "risk_indicators": ["raises risk: product 731815 was fraudulent in 45% of its 1,200 past declarations (average 22%)"],
         "date": "2021-06-12"}
VOCAB = Vocab(origins={"CN", "JP", "KR", "DE", "TR", "IN", "VN"}, offices={"20": "Incheon", "30": "Busan", "40": "Airport"},
              hs6={"851712", "850131", "620439", "610910", "300490", "870323", "950300", "090111"},
              importers={"ABC1234"}, date_min="2021-04-01", date_max="2021-06-30")


def test_number_guard_catches_invented_number():
    assert unmatched_numbers("Le risque est de 93 %.", FACTS) == ["93"]


def test_number_guard_accepts_formatted_equivalents():
    ok = ("Risque de 71,8 % (soit 72 %), produit 731815 frauduleux dans 45 % de ses 1 200 déclarations, "
          "moyenne 0,22, déclaration 54794554 du 2021-06-12.")
    assert unmatched_numbers(ok, FACTS) == []
    assert unmatched_numbers("risk 0.718 and 1,200 declarations", FACTS) == []


def test_number_guard_handles_arabic_indic_digits():
    assert unmatched_numbers("خطر الغش ٧١٫٨٪ في ١٢٠٠ تصريح", FACTS) == []
    assert unmatched_numbers("خطر الغش ٩٣٪", FACTS) == ["93"]


def test_banned_claims():
    assert banned_claims("These goods are fraudulent and must be seized.")
    assert banned_claims("La marchandise est frauduleuse.")
    assert not banned_claims("Several risk indicators suggest a document check.")


def test_nlq_validation_drops_invalid_values():
    f, w = validate({"lane": ["RED", "PURPLE"], "origin": ["CN", "XX", "China"], "office": ["30", "999"],
                     "hs_prefix": ["85", "9"], "min_fraud": 80, "date_from": "2020-01-01", "limit": 5000}, VOCAB)
    assert f.lane == ["RED"] and f.origin == ["CN"] and f.office == ["30"] and f.hs_prefix == ["85"]
    assert f.min_fraud == 0.8 and f.limit == 500 and f.date_from is None
    assert len(w) >= 4


def test_rules_parser_fr_en_ar():
    assert rules_parse("déclarations rouges d'origine CN au chapitre 85 au-dessus de 80%", VOCAB) == \
        {"lane": ["RED"], "min_fraud": 0.8, "origin": ["CN"], "hs_prefix": ["85"]}
    assert rules_parse("show uncertain cases from office 20", VOCAB) == {"uncertain_only": True, "office": ["20"]}
    assert rules_parse("الحالات ذات التنبيه الأمني", VOCAB) == {"safety_only": True, "sort": "critical_desc"}


def test_nlq_falls_back_to_rules_on_timeout(monkeypatch):
    monkeypatch.setattr(client, "available", lambda: True)

    def boom(*a, **k):
        raise client.LLMError("timed out")
    monkeypatch.setattr(client, "chat", boom)
    r = parse("red declarations from China above 90%", VOCAB)
    assert r["source"] == "rules" and r["filter"]["origin"] == ["CN"] and r["warnings"]


def test_brief_falls_back_to_template_on_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(LB, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(client, "available", lambda: True)

    def boom(*a, **k):
        raise client.LLMError("timed out")
    monkeypatch.setattr(client, "chat", boom)
    b = LB.brief("54794554", "fr", FACTS, "TEMPLATE TEXT", refresh=True)
    assert b["source"] == "template" and b["text"] == "TEMPLATE TEXT" and b["guard_passed"] is False


def test_brief_guard_rejects_then_accepts(monkeypatch, tmp_path):
    monkeypatch.setattr(LB, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(client, "available", lambda: True)
    good = ("Cette déclaration présente plusieurs indicateurs de risque. Le risque de fraude estimé est de 71,8 %. "
            "Le produit 731815 a été frauduleux dans 45 % de ses 1 200 déclarations passées, contre 22 % en moyenne. "
            "Le risque pour la sécurité est faible et la décision revient à l'agent.")
    answers = iter([json.dumps({"brief": "Le risque est de 93 % et les biens sont certainement frauduleux.", "suggested_check": "valeur"}),
                    json.dumps({"brief": good, "suggested_check": "vérifier la facture et la valeur déclarée"})])
    monkeypatch.setattr(client, "chat", lambda *a, **k: (next(answers), 1234))
    b = LB.brief("54794554", "fr", FACTS, "TEMPLATE", refresh=True)
    assert b["source"] == "qwen3-4b" and b["guard_passed"] and "Contrôle suggéré" in b["text"]


@pytest.fixture(scope="module")
def off_client(built):
    import os
    os.environ["RAQIB_LLM"] = "off"
    from raqib.llm import config as K
    K.MODE_ENV = "off"
    client._state["checked"] = False
    from raqib.api import app
    with TestClient(app) as c:
        yield c
    os.environ.pop("RAQIB_LLM", None)
    K.MODE_ENV = ""
    client._state["checked"] = False


def test_endpoints_work_with_llm_off(off_client):
    st = off_client.get("/api/llm/status").json()
    assert st["enabled"] is False and st["mode"] == "off"
    wl = off_client.get("/api/worklist", params={"lane": "RED", "page_size": 1}).json()
    did = wl["items"][0]["id"]
    for lang in ("fr", "ar", "en"):
        b = off_client.post("/api/brief", json={"id": did, "lang": lang}).json()
        assert b["source"] == "template" and b["text"] and b["dir"] == ("rtl" if lang == "ar" else "ltr")
    r = off_client.post("/api/nlq", json={"q": "déclarations rouges d'origine CN au chapitre 85 au-dessus de 80%"}).json()
    assert r["source"] == "rules" and r["filter"]["lane"] == ["RED"] and "HS 85" in r["explanation"]
    q = off_client.post("/api/worklist/query", json={"filter": r["filter"]}).json()
    assert all(i["lane"] == "RED" and i["origin"] == "CN" and i["hs6"].startswith("85") and i["p_fraud"] >= 0.8 for i in q["items"])
    assert off_client.get("/api/llm/eval").status_code == 200
