import pytest
from fastapi.testclient import TestClient

from raqib import config as C


@pytest.fixture(scope="module")
def client(built):
    from raqib.api import app
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["models_loaded"] is True
    assert body["n_test_declarations"] == 8481
    assert body["n_days"] == 91


def test_data_card_and_metrics(client):
    card = client.get("/api/data-card").json()
    assert card["test"]["rows"] == 8481
    m = client.get("/api/metrics").json()
    assert set(m["targets"]) == {"fraud", "critical"}
    assert m["n_critical_test"] == 73
    assert "fairness" in m and "replay_summary" in m


def test_replay_all_policies_same_capacity(client):
    r = client.get("/api/replay", params={"rate": 0.05, "explore": 0.1}).json()
    assert set(r["policies"]) == {"ai", "ai_explore", "rule", "random"}
    caps = {p: v["cum_inspected"][-1] for p, v in r["policies"].items()}
    assert len(set(caps.values())) == 1
    assert client.get("/api/replay", params={"rate": 0.9}).status_code == 422


def test_stream_and_declaration(client):
    s = client.get("/api/stream", params={"day": 4}).json()
    assert s["n"] == len(s["items"]) > 0
    red = [i for i in s["items"] if i["lane"] == "RED"]
    assert len(red) == s["capacity"]
    d = client.get(f"/api/declaration/{red[0]['id']}").json()
    assert d["ai"]["lane"] == "RED"
    assert len(d["ai"]["reasons_fraud"]) == 4
    assert len(d["ai"]["reasons_critical"]) == 2
    assert d["rule"]["decision"] in {"INSPECT", "RELEASE"}
    assert {"importer", "declarant", "seller"} <= set(d["history"])
    assert 0 < len(d["network"]["nodes"]) <= 25
    assert client.get("/api/declaration/nope").status_code == 404
    assert client.get("/api/stream", params={"day": 500}).status_code == 404


def test_presets_and_score(client):
    presets = client.get("/api/presets").json()
    assert [p["key"] for p in presets] == ["high_fraud", "safety_alert", "low_risk"]
    for p in presets:
        r = client.post("/api/score", json=p["declaration"])
        assert r.status_code == 200
        assert r.json()["lane"] in {"RED", "YELLOW", "GREEN"}
    new = client.post("/api/score", json={"hs6": "621149", "origin": "CN", "office": 40, "tax_rate": 13,
                                          "net_mass": 45, "item_price": 12300, "transport": 40}).json()
    assert any("New importer" in n for n in new["notes"])
    assert client.post("/api/score", json={"hs6": "abc"}).status_code == 422


def test_hs_search(client):
    res = client.get("/api/hs/search", params={"q": "coffee"}).json()
    assert 0 < len(res) <= 20
    assert all("coffee" in r["description"].lower() or r["hs6"].startswith("coffee") for r in res)


def test_decisions_chain(client, tmp_path, monkeypatch):
    monkeypatch.setattr(C, "DECISIONS_LOG", tmp_path / "decisions.jsonl")
    s = client.get("/api/stream", params={"day": 2}).json()
    did = s["items"][0]["id"]
    r1 = client.post("/api/decision", json={"declaration_id": did, "decision": "INSPECT",
                                            "comment": "demo", "officer": "Officer A"}).json()
    r2 = client.post("/api/decision", json={"declaration_id": did, "decision": "RELEASE",
                                            "comment": "", "officer": "Officer B"}).json()
    assert r2["prev_hash"] == r1["hash"]
    log = client.get("/api/decisions").json()
    assert log["verify"]["ok"] and log["verify"]["n_entries"] == 2
    assert client.post("/api/decision", json={"declaration_id": did, "decision": "MAYBE"}).status_code == 422
