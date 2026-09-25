"""`python -m raqib.build` - data, models, measured results, explanations and replay.

Writes to artifacts/: data_card.json, models/*, metrics.json, test_scored.parquet,
replay_default.json. Prints the metric table and the replay summary.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from . import config as C
from . import evaluate as E
from . import replay as R
from .baselines import baseline_scores
from .data import data_available, download, hs_description, load_test, load_train, write_data_card
from .explain import GROUP_DEFS, explain_frame
from .model import fit_target, hs6_unit_context


def _t(msg: str, t0: float) -> None:
    print(f"[build] {msg:<44s} {time.time() - t0:6.1f}s", flush=True)


def build_test_scored(test: pd.DataFrame, res: dict, rules: dict, reasons: dict) -> pd.DataFrame:
    fr, cr = res["fraud"], res["critical"]
    ts = pd.DataFrame({
        "declaration_id": test["Declaration ID"].astype(str).to_numpy(),
        "date": test["Date"].dt.strftime("%Y-%m-%d").to_numpy(),
        "hs6": test["HS6 Code"].to_numpy(int),
        "hs_desc": test["HS6 Code"].map(hs_description).to_numpy(),
        "office": test["Office ID"].to_numpy(int),
        "office_label": test["Office ID"].map(C.office_label).to_numpy(),
        "transport": test["Mode of Transport"].to_numpy(int),
        "transport_label": test["Mode of Transport"].map(C.transport_label).to_numpy(),
        "origin": test["Country of Origin"].to_numpy(),
        "departure": test["Country of Departure"].to_numpy(),
        "importer": test["Importer ID"].to_numpy(),
        "declarant": test["Declarant ID"].to_numpy(),
        "seller": test["Seller ID"].to_numpy(),
        "courier": test["Courier ID"].fillna("").to_numpy(),
        "process_type": test["Process Type"].to_numpy(),
        "import_type": test["Import Type"].to_numpy(int),
        "import_use": test["Import Use"].to_numpy(int),
        "payment_type": test["Payment Type"].to_numpy(int),
        "tax_type": test["Tax Type"].to_numpy(),
        "origin_indicator": test["Country of Origin Indicator"].to_numpy(),
        "tax_rate": test["Tax Rate"].to_numpy(float),
        "net_mass": test["Net Mass"].to_numpy(float),
        "item_price": test["Item Price"].to_numpy(float),
        "fraud": test["fraud"].to_numpy(int),
        "critical": test["critical"].to_numpy(int),
        "critical_code": test["Critical Fraud"].to_numpy(int),
        "score_fraud": fr["raw"],
        "p_fraud": fr["cal"],
        "score_critical": cr["raw"],
        "p_critical": cr["cal"],
        "rule_score": rules["fraud"]["rule_hs6_history"],
        "rule_score_critical": rules["critical"]["rule_hs6_history"],
        "rule_importer_score": rules["fraud"]["rule_importer_history"],
    })
    ts["reasons_fraud"] = [json.dumps(r, ensure_ascii=False) for r in reasons["fraud"]]
    ts["reasons_critical"] = [json.dumps(r, ensure_ascii=False) for r in reasons["critical"]]
    ts["top_reason"] = [r[0]["text"] if r else "" for r in reasons["fraud"]]
    return ts


def main() -> None:
    t0 = time.time()
    C.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    C.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if not data_available():
        download()
    train, test = load_train(), load_test()
    card = write_data_card()
    _t(f"data: TRAIN {len(train):,} rows, TEST {len(test):,} rows", t0)

    res: dict = {}
    for target in C.TARGETS:
        tm, X_tr, oof = fit_target(train, target)
        tm.save()
        X_te = tm.features(test)
        raw = tm.raw(X_te)
        res[target] = {"tm": tm, "X_te": X_te, "raw": raw, "cal": tm.calibrate(raw), "oof": oof}
        _t(f"model '{target}' trained + calibrated", t0)

    context = hs6_unit_context(train)
    raw_f, raw_c = res["fraud"]["raw"], res["critical"]["raw"]
    tm_f, tm_c = res["fraud"]["tm"], res["critical"]["tm"]
    th = {
        "alert_threshold": float(np.quantile(raw_c, C.ALERT_QUANTILE)),
        "red_threshold": float(np.quantile(raw_f, 1 - C.DEFAULT_RATE)),
        "yellow_threshold": float(np.quantile(raw_f, 1 - C.DEFAULT_RATE - C.YELLOW_SHARE)),
        "note": "Thresholds on raw model scores taken from the TEST period: alert = 99th pct of "
                "critical score; RED = 95th pct and YELLOW = 85th pct of fraud score.",
    }
    th["alert_p_critical"] = float(tm_c.calibrate(np.array([th["alert_threshold"]]))[0])
    th["red_p_fraud"] = float(tm_f.calibrate(np.array([th["red_threshold"]]))[0])
    th["yellow_p_fraud"] = float(tm_f.calibrate(np.array([th["yellow_threshold"]]))[0])
    (C.MODELS_DIR / "thresholds.json").write_text(json.dumps(th, indent=2), encoding="utf-8")
    joblib.dump({**context, "test_sorted_fraud": np.sort(raw_f), "test_sorted_critical": np.sort(raw_c)},
                C.MODELS_DIR / "context.joblib")

    # ---- measured results ------------------------------------------------------
    tb = E.tiebreak_for(len(test))
    rules = {t: baseline_scores(train, test, t) for t in C.TARGETS}
    metrics: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "recipe": {
            "train": card["train"]["period"], "test": card["test"]["period"],
            "n_train": card["train"]["rows"], "n_test": card["test"]["rows"],
            "features": C.FEATURES, "lgbm_params": C.LGBM_PARAMS, "smoothing_a": C.TARGETS,
            "topk": "k = ceil(share x n); ties broken by one fixed random permutation (seed 0)",
        },
        "method_labels": E.METHOD_LABELS,
        "targets": {},
    }
    for target in C.TARGETS:
        y = test[target].to_numpy(int)
        scores = {"ai": res[target]["raw"], **rules[target]}
        t_out = {
            "label": E.TARGET_LABELS[target],
            "base_rate": float(y.mean()),
            "n_positive": int(y.sum()),
            "prior_train": float(res[target]["tm"].prior),
            "methods": {m: E.method_metrics(y, scores[m], tb) for m in E.METHODS},
            "calibration": E.calibration_table(y, res[target]["cal"], res[target]["raw"]),
            "weekly": E.weekly_table(test["Date"], y, {"ai": scores["ai"], "rule": scores["rule_hs6_history"]}, tb),
            "importance": E.importance(res[target]["tm"], GROUP_DEFS),
            "gain_vs_rule": E.paired_gain_ci(
                y, scores["ai"], scores["rule_hs6_history"], tb, frac=0.05,
                metric="precision" if target == "fraud" else "recall"),
        }
        metrics["targets"][target] = t_out
    # ablation: same recipe without the value/mass features (does price carry signal here?)
    from lightgbm import LGBMClassifier
    from .model import build_X, oof_encode
    value_feats = ["net_mass", "item_price", "unit"]
    keep = [f for f in C.FEATURES if f not in value_feats]
    metrics["ablation_no_value"] = {"removed": value_feats}
    for target in C.TARGETS:
        y_tr = train[target].to_numpy(int)
        tm = res[target]["tm"]
        X_tr = build_X(oof_encode(train, y_tr, tm.a, tm.prior), train)[keep]
        mdl = LGBMClassifier(**C.LGBM_PARAMS).fit(X_tr, y_tr)
        s_ab = mdl.predict_proba(res[target]["X_te"][keep])[:, 1]
        mm = E.method_metrics(test[target].to_numpy(int), s_ab, tb)
        metrics["ablation_no_value"][target] = {k: mm[k] for k in ("auc", "precision_at_5", "recall_at_5")}
    metrics["fairness"] = E.fairness(test, test["fraud"].to_numpy(int), raw_f, rules["fraud"]["rule_hs6_history"], tb)
    metrics["n_critical_test"] = int(test["critical"].sum())
    metrics["thresholds"] = th
    _t("metrics computed", t0)

    # ---- explanations + scored TEST ----------------------------------------------
    reasons = {t: explain_frame(res[t]["tm"], test, context, X=res[t]["X_te"]) for t in C.TARGETS}
    _t("explanations (TreeSHAP) for every TEST row", t0)
    ts = build_test_scored(test, res, rules, reasons)
    rd = R.prepare(ts, alert_thr=th["alert_threshold"])
    lanes = R.lanes_for(rd, C.DEFAULT_RATE, 0.0)
    ts["lane"] = lanes["lane"].astype(str)
    ts["alert"] = lanes["alert"]
    ts["rule_selected"] = lanes["rule_selected"]
    ts.to_parquet(C.ARTIFACTS / "test_scored.parquet", index=False)

    # ---- replay ------------------------------------------------------------------
    runs = {f"{e:.1f}": R.replay(rd, rate=C.DEFAULT_RATE, explore=e) for e in (0.0, C.DEFAULT_EXPLORE)}
    (C.ARTIFACTS / "replay_default.json").write_text(json.dumps({"runs": runs}), encoding="utf-8")
    main_run = runs[f"{C.DEFAULT_EXPLORE:.1f}"]
    metrics["replay_summary"] = {
        "rate": C.DEFAULT_RATE, "explore": C.DEFAULT_EXPLORE,
        "totals": main_run["totals"], "n_days": main_run["n_days"],
        "policies": {p: {"label": v["label"], **v["summary"]} for p, v in main_run["policies"].items()},
    }
    (C.ARTIFACTS / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    _t("test_scored.parquet + replay_default.json written", t0)

    # ---- console report -------------------------------------------------------------
    print("\n".join(E.metric_rows(metrics)))
    for target in C.TARGETS:
        g = metrics["targets"][target]["gain_vs_rule"]
        print(f"  gain AI - rule ({target}, {g['metric']}): {g['mean_gain']:+.3f} "
              f"[95% CI {g['ci95'][0]:+.3f}, {g['ci95'][1]:+.3f}]")
    print("\n".join(R.summary_table(main_run)))
    try:  # keep README numbers and docs/*.md in sync with the artifacts
        from . import report
        report.main()
    except Exception as exc:  # noqa: BLE001 - docs must never break the build
        print(f"[build] WARNING: report generation failed: {exc}")
    print(f"\n[build] done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
