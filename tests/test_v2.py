"""v2: glass-box twin, waterfalls, uncertainty, worklist, what-if, efficiency, experiments, model card, brief."""
import json
import re
import time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from raqib import config as C


@pytest.fixture(scope="module")
def client(built):
    from raqib.api import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def ts(built):
    return pd.read_parquet(C.ARTIFACTS / "test_scored.parquet")


def test_ebm_contributions_are_exact(built):
    from raqib.twin import load_twins
    from raqib.data import load_test
    twin = load_twins()["fraud"]
    test = load_test().head(300)
    X = twin.features(test)
    G, base, _ = twin.contributions(X, model="ebm")
    logit = base + G.sum(axis=1)
    p = twin.ebm.predict_proba(X)[:, 1]
    assert np.allclose(1 / (1 + np.exp(-logit)), p, atol=1e-6)


def test_waterfall_final_matches_probability(ts):
    m = json.loads((C.ARTIFACTS / "metrics.json").read_text(encoding="utf-8"))
    for _, r in ts.sample(50, random_state=0).iterrows():
        w = json.loads(r["waterfall_fraud"])
        if m["primary_model"]["fraud"] == "ebm":
            assert abs(w["final"] - r["p_fraud"]) < 2e-4
        steps = [w["base"]] + [s["cumulative"] for s in w["steps"]]
        assert abs(steps[-1] + w["other"]["delta"] - w["final"]) < 2e-4


def test_primary_rule_and_uncertainty(ts):
    m = json.loads((C.ARTIFACTS / "metrics.json").read_text(encoding="utf-8"))
    for target, key in (("fraud", "precision_at_5"), ("critical", "recall_at_5")):
        meth = m["targets"][target]["methods"]
        expected = "ebm" if meth["ebm"][key] >= meth["lightgbm"][key] - 0.015 else "lightgbm"
        assert m["primary_model"][target] == expected
    assert not ((ts["lane"] == "GREEN") & ts["uncertain"]).any()  # never released green
    u = m["uncertainty"]
    assert u["n_flagged"] == int(ts["uncertain"].sum())


def test_declaration_and_stream_v2_fields(client, ts):
    did = ts["declaration_id"].iloc[0]
    d = client.get(f"/api/declaration/{did}").json()
    assert {"uncertain", "disagreement", "models"} <= set(d["ai"])
    assert d["waterfall"]["steps"] and "final" in d["waterfall_critical"]
    item = client.get("/api/stream", params={"day": 3}).json()["items"][0]
    assert "uncertain" in item and "disagreement" in item


def test_worklist_filters_and_pages(client):
    r = client.get("/api/worklist", params={"lane": "RED", "page_size": 20, "sort": "p_fraud"}).json()
    assert r["total"] == 470 and len(r["items"]) == 20
    assert all(i["lane"] == "RED" for i in r["items"])
    ps = [i["p_fraud"] for i in r["items"]]
    assert ps == sorted(ps, reverse=True)
    r2 = client.get("/api/worklist", params={"day": 4, "page": 2, "page_size": 10}).json()
    assert r2["page"] == 2 and all(i["day"] == 4 for i in r2["items"])
    assert client.get("/api/worklist", params={"sort": "nope"}).status_code == 422


def test_whatif_fast_and_consistent(client, ts):
    did = ts["declaration_id"].iloc[10]
    t0 = time.time()
    r = client.post("/api/whatif", json={"declaration_id": did, "changes": {"importer": "new", "item_price": 12345}})
    assert r.status_code == 200 and (time.time() - t0) < 1.0
    body = r.json()
    assert set(body["changed"]) == {"importer", "item_price"}
    assert abs(body["before"]["p_fraud"] - float(ts["p_fraud"].iloc[10])) < 1e-6  # before = stored score
    same = client.post("/api/whatif", json={"declaration_id": did, "changes": {}}).json()
    assert same["before"]["p_fraud"] == same["after"]["p_fraud"] and same["deltas"] == []


def test_efficiency_experiments_xai_modelcard(client):
    e = client.get("/api/efficiency", params={"minutes_per_inspection": 30}).json()
    mt = e["matching"]
    assert mt["ai_frauds"] >= mt["reference"]["frauds"] and mt["ai_inspections"] < mt["reference"]["inspections"]
    assert e["officer_hours"]["minutes_per_inspection"] == 30 and e["officer_hours"]["assumption"] is True
    assert len(e["curve"]) == 20
    ex = client.get("/api/experiments").json()["experiments"]
    assert {x["key"] for x in ex} == {"ebm", "disagreement", "isolation_forest", "network_2hop"}
    xg = client.get("/api/xai-global").json()
    assert xg["targets"]["fraud"]["shapes"] and xg["targets"]["fraud"]["importances"]
    mc = client.get("/api/model-card").json()
    assert "out_of_scope" in [s["key"] for s in mc["sections"]]


def test_brief_numbers_come_from_facts(client, ts):
    did = ts.sort_values("p_fraud", ascending=False)["declaration_id"].iloc[0]
    for lang in ("fr", "en", "ar"):
        b = client.post(f"/api/brief/{did}", params={"lang": lang}).json()
        assert b["source"] == "template" and len(b["text"]) > 50
        facts_blob = json.dumps(b["facts"])
        for num in re.findall(r"\d+(?:[.,]\d+)?", b["text"]):
            v = float(num.replace(",", "."))
            # every number is a fact (as %, count, code or percentile) or a constant of the template
            assert v in (1, 5) or any(abs(v - x) < 0.6 or abs(v - 100 * x) < 0.6 for x in
                                      [float(y) for y in re.findall(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", facts_blob)]), (lang, num)
