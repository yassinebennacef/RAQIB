import json

import numpy as np
import pandas as pd

from raqib import config as C
from raqib import decisions as D
from raqib import replay as R
from raqib.data import hs_description, load_test, load_train
from raqib.model import TargetEncoder


def test_data_splits():
    train, test = load_train(), load_test()
    assert len(train) == 45_519
    assert len(test) == 8_481
    assert train["Date"].max() < test["Date"].min()
    assert int(test["critical"].sum()) == 73


def test_hs_names():
    assert "Coffee" in hs_description(90121)
    assert hs_description(979797) == "HS 979797"


def test_encoder_smoothing_and_unknowns():
    df = pd.DataFrame({col: ["x", "x", "y"] for col, _ in C.KEYS})
    enc = TargetEncoder.fit(df, np.array([1, 0, 1]), a=10, prior=0.2)
    new = pd.DataFrame({col: ["x", "zzz"] for col, _ in C.KEYS})
    out = enc.transform(new)
    assert np.isclose(out["rate_hs6"].iloc[0], (1 + 10 * 0.2) / (2 + 10))
    assert out["count_hs6"].iloc[1] == 0
    assert np.isclose(out["rate_hs6"].iloc[1], 0.2)  # unknown -> prior


def test_metrics_exist_and_ai_beats_rule(built):
    m = json.loads((C.ARTIFACTS / "metrics.json").read_text(encoding="utf-8"))
    fraud = m["targets"]["fraud"]["methods"]
    crit = m["targets"]["critical"]["methods"]
    assert fraud["ai"]["precision_at_5"] > fraud["rule_hs6_history"]["precision_at_5"]
    assert crit["ai"]["recall_at_5"] > crit["rule_hs6_history"]["recall_at_5"]
    assert m["n_critical_test"] == 73
    for t in ("fraud", "critical"):
        assert len(m["targets"][t]["calibration"]) == 10
        assert len(m["targets"][t]["weekly"]) == 13


def test_replay_capacity_identical_across_policies(built):
    ts = pd.read_parquet(C.ARTIFACTS / "test_scored.parquet")
    d = R.prepare(ts)
    for rate, explore in [(0.05, 0.0), (0.05, 0.1), (0.12, 0.1)]:
        r = R.replay(d, rate=rate, explore=explore)
        insp = {p: v["cum_inspected"] for p, v in r["policies"].items()}
        first = next(iter(insp.values()))
        assert all(v == first for v in insp.values())
        assert first[-1] == sum(r["capacity"])
    r = R.replay(d, rate=0.05, explore=0.1)
    assert r["policies"]["ai_explore"]["summary"]["explored"] > 0
    assert r["policies"]["ai"]["summary"]["explored"] == 0


def test_score_new_known_and_unknown(built):
    from raqib.score import score_new
    ts = pd.read_parquet(C.ARTIFACTS / "test_scored.parquet")
    row = ts.iloc[0]
    known = score_new({
        "hs6": int(row["hs6"]), "origin": row["origin"], "office": int(row["office"]),
        "importer_id": row["importer"], "declarant_id": row["declarant"], "seller_id": row["seller"],
        "tax_rate": float(row["tax_rate"]), "net_mass": float(row["net_mass"]),
        "item_price": float(row["item_price"]), "transport": int(row["transport"]),
    })
    assert np.isclose(known["p_fraud"], row["p_fraud"], atol=1e-9)
    assert known["lane"] in {"RED", "YELLOW", "GREEN"}
    assert len(known["reasons_fraud"]) == 4
    unknown = score_new({"hs6": "621149", "origin": "CN", "office": 40, "importer_id": "",
                         "declarant_id": "", "seller_id": "", "tax_rate": 13, "net_mass": 45,
                         "item_price": 12300, "transport": 40})
    assert 0 <= unknown["p_fraud"] <= 1
    assert any("New importer" in n for n in unknown["notes"])


def test_decision_chain_detects_tampering(tmp_path):
    log = tmp_path / "decisions.jsonl"
    D.append("1", "INSPECT", "check invoice", "Officer A", path=log)
    D.append("2", "RELEASE", "", "Officer B", path=log)
    D.append("3", "DOCUMENT_CHECK", "origin proof", "Officer A", path=log)
    assert D.verify(log)["ok"]
    lines = log.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[1])
    rec["decision"] = "INSPECT"
    lines[1] = json.dumps(rec)
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    v = D.verify(log)
    assert not v["ok"] and v["first_bad_id"] == 2
