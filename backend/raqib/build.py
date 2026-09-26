"""`python -m raqib.build` - data, models, measured results, explanations, replay and v2 analyses.

Writes to artifacts/: data_card.json, models/* (LightGBM + cached EBM twins), metrics.json,
test_scored.parquet, replay_default.json, efficiency.json, experiments.json, xai_global.json,
model_card.json (+ docs via raqib.report). Prints the metric table and the replay summary.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd

from . import config as C
from . import efficiency as EF
from . import evaluate as E
from . import experiments as EX
from . import replay as R
from . import xai as XAI
from .baselines import baseline_scores
from .data import data_available, download, hs_description, load_test, load_train, save_hs_names, write_data_card
from .explain import GROUP_DEFS, explain_frame, waterfall
from .model import fit_ebm_cached, fit_shadow_pair, fit_target, hs6_unit_context
from .twin import MODEL_LABELS, PRIMARY_RULE, Twin, choose_primary, save_primary


def _t(msg: str, t0: float) -> None:
    print(f"[build] {msg:<48s} {time.time() - t0:6.1f}s", flush=True)


def build_test_scored(test: pd.DataFrame, res: dict, rules: dict, reasons: dict, waterfalls: dict) -> pd.DataFrame:
    fr, cr = res["fraud"]["pred"], res["critical"]["pred"]
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
        # primary model (drives lanes and replay)
        "score_fraud": fr["score"],
        "p_fraud": fr["p"],
        "score_critical": cr["score"],
        "p_critical": cr["p"],
        # both twins
        "p_fraud_lgbm": fr["lgbm_p"], "raw_fraud_lgbm": fr["lgbm_raw"], "p_fraud_ebm": fr["ebm_p"],
        "p_critical_lgbm": cr["lgbm_p"], "raw_critical_lgbm": cr["lgbm_raw"], "p_critical_ebm": cr["ebm_p"],
        "disagreement": res["fraud"]["disagreement"],
        "uncertain": res["fraud"]["uncertain"],
        "rule_score": rules["fraud"]["rule_hs6_history"],
        "rule_score_critical": rules["critical"]["rule_hs6_history"],
        "rule_importer_score": rules["fraud"]["rule_importer_history"],
    })
    ts["reasons_fraud"] = [json.dumps(r, ensure_ascii=False) for r in reasons["fraud"]]
    ts["reasons_critical"] = [json.dumps(r, ensure_ascii=False) for r in reasons["critical"]]
    ts["top_reason"] = [r[0]["text"] if r else "" for r in reasons["fraud"]]
    ts["waterfall_fraud"] = [json.dumps(w) for w in waterfalls["fraud"]]
    ts["waterfall_critical"] = [json.dumps(w) for w in waterfalls["critical"]]
    return ts


def _p_at(twin: Twin, score: float) -> float:
    """Probability shown for a primary-model score threshold."""
    if twin.primary == "ebm":
        return float(score)
    return float(twin.lgbm.calibrate(np.array([score]))[0])


def main() -> None:
    t0 = time.time()
    C.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    C.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if not data_available():
        download()
    train, test = load_train(), load_test()
    card = write_data_card()
    save_hs_names()
    from .engine import TRAIN_INDEX, build_train_index
    joblib.dump(build_train_index(train), TRAIN_INDEX)
    _t(f"data: TRAIN {len(train):,} rows, TEST {len(test):,} rows", t0)

    tb = E.tiebreak_for(len(test))
    res: dict = {}
    primary: dict[str, str] = {}
    m_lgbm: dict = {}
    m_ebm: dict = {}
    for target in C.TARGETS:
        tm, X_tr, oof = fit_target(train, target)
        tm.save()
        y_tr = train[target].to_numpy(int)
        ebm, info = fit_ebm_cached(target, X_tr, y_tr)
        X_te = tm.features(test)
        y = test[target].to_numpy(int)
        m_lgbm[target] = E.method_metrics(y, tm.raw(X_te), tb)
        m_ebm[target] = E.method_metrics(y, ebm.predict_proba(X_te)[:, 1], tb)
        primary[target] = choose_primary(m_lgbm[target], m_ebm[target], target)
        twin = Twin(target, tm, ebm, primary[target])
        res[target] = {"tm": tm, "twin": twin, "X_tr": X_tr, "X_te": X_te, "pred": twin.predict(X_te),
                       "ebm_fit": info}
        _t(f"'{target}': LightGBM + EBM ({info['fit_seconds']}s fit, cached) -> primary {primary[target]}", t0)
    save_primary(primary)

    # ---- uncertainty: disagreement threshold measured out-of-sample on the last 4 TRAIN weeks -------------
    sh = fit_shadow_pair(train, "fraud")
    d_late = np.abs(sh["p_ebm"] - sh["p_lgbm"])
    d_thr = float(np.quantile(d_late, 0.95))
    pf = res["fraud"]["pred"]
    disagreement = np.abs(pf["ebm_p"] - pf["lgbm_raw"])
    res["fraud"]["disagreement"] = disagreement
    res["fraud"]["uncertain"] = disagreement > d_thr
    _t(f"disagreement threshold {d_thr:.3f} (shadow models, {sh['late_period'][0]}..)", t0)

    # ---- thresholds on primary scores -------------------------------------------------------------------
    context = hs6_unit_context(train)
    s_f, s_c = res["fraud"]["pred"]["score"], res["critical"]["pred"]["score"]
    tw_f, tw_c = res["fraud"]["twin"], res["critical"]["twin"]
    th = {
        "alert_threshold": float(np.quantile(s_c, C.ALERT_QUANTILE)),
        "red_threshold": float(np.quantile(s_f, 1 - C.DEFAULT_RATE)),
        "yellow_threshold": float(np.quantile(s_f, 1 - C.DEFAULT_RATE - C.YELLOW_SHARE)),
        "disagreement_threshold": d_thr,
        "primary": primary,
        "note": "Thresholds on the primary models' scores from the TEST period: alert = 99th pct of the critical "
                "score; RED = 95th pct and YELLOW = 85th pct of the fraud score. Disagreement threshold = 95th pct "
                "of |p(EBM) - p(LightGBM)| on the last 4 training weeks (models trained without those weeks).",
    }
    th["alert_p_critical"] = _p_at(tw_c, th["alert_threshold"])
    th["red_p_fraud"] = _p_at(tw_f, th["red_threshold"])
    th["yellow_p_fraud"] = _p_at(tw_f, th["yellow_threshold"])
    (C.MODELS_DIR / "thresholds.json").write_text(json.dumps(th, indent=2), encoding="utf-8")
    joblib.dump({**context, "test_sorted_fraud": np.sort(s_f), "test_sorted_critical": np.sort(s_c)},
                C.MODELS_DIR / "context.joblib")

    # ---- measured results -------------------------------------------------------------------------------
    rules = {t: baseline_scores(train, test, t) for t in C.TARGETS}
    labels = dict(E.METHOD_LABELS)
    labels["ai"] = f"RAQIB AI ({MODEL_LABELS[primary['fraud']].split(' (')[0]} primary)"
    labels["lightgbm"] = "LightGBM (black box)"
    labels["ebm"] = "EBM (glass box)"
    metrics: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "recipe": {
            "train": card["train"]["period"], "test": card["test"]["period"],
            "n_train": card["train"]["rows"], "n_test": card["test"]["rows"],
            "features": C.FEATURES, "lgbm_params": C.LGBM_PARAMS, "smoothing_a": C.TARGETS,
            "ebm_params": {k: v for k, v in res["fraud"]["ebm_fit"]["params"].items() if k != "n_jobs"},
            "topk": "k = ceil(share x n); ties broken by one fixed random permutation (seed 0)",
        },
        "method_labels": labels,
        "primary_model": {**primary, "rule": PRIMARY_RULE},
        "targets": {},
    }
    for target in C.TARGETS:
        y = test[target].to_numpy(int)
        pred = res[target]["pred"]
        twin = res[target]["twin"]
        scores = {"ai": pred["score"], **rules[target]}
        methods = {m: E.method_metrics(y, scores[m], tb) for m in E.METHODS}
        methods["lightgbm"], methods["ebm"] = m_lgbm[target], m_ebm[target]
        metric = "precision" if target == "fraud" else "recall"
        metrics["targets"][target] = {
            "label": E.TARGET_LABELS[target],
            "base_rate": float(y.mean()),
            "n_positive": int(y.sum()),
            "prior_train": float(twin.prior),
            "primary": primary[target],
            "methods": methods,
            "calibration": E.calibration_table(y, pred["p"], pred["score"]),
            "calibration_models": {"lightgbm": E.calibration_table(y, pred["lgbm_p"], pred["lgbm_raw"]),
                                   "ebm": E.calibration_table(y, pred["ebm_p"], pred["ebm_p"])},
            "weekly": E.weekly_table(test["Date"], y, {"ai": scores["ai"], "rule": scores["rule_hs6_history"]}, tb),
            "importance": (E.ebm_importance(twin.ebm) if primary[target] == "ebm"
                           else E.importance(twin.lgbm, GROUP_DEFS)),
            "importance_models": {"lightgbm": E.importance(twin.lgbm, GROUP_DEFS), "ebm": E.ebm_importance(twin.ebm)},
            "gain_vs_rule": E.paired_gain_ci(y, scores["ai"], scores["rule_hs6_history"], tb, frac=0.05, metric=metric),
            "ebm_vs_lightgbm": E.paired_gain_ci(y, pred["ebm_p"], pred["lgbm_raw"], tb, frac=0.05, metric=metric),
        }

    # ablation: LightGBM without the value/mass features (does price carry signal here?)
    from lightgbm import LGBMClassifier
    value_feats = ["net_mass", "item_price", "unit"]
    keep = [f for f in C.FEATURES if f not in value_feats]
    metrics["ablation_no_value"] = {"removed": value_feats, "model": "lightgbm"}
    for target in C.TARGETS:
        y_tr = train[target].to_numpy(int)
        mdl = LGBMClassifier(**C.LGBM_PARAMS).fit(res[target]["X_tr"][keep], y_tr)
        mm = E.method_metrics(test[target].to_numpy(int), mdl.predict_proba(res[target]["X_te"][keep])[:, 1], tb)
        full = m_lgbm[target]
        metrics["ablation_no_value"][target] = {
            **{k: mm[k] for k in ("auc", "precision_at_5", "recall_at_5")},
            **{f"full_{k}": full[k] for k in ("auc", "precision_at_5", "recall_at_5")},
        }
    metrics["fairness"] = E.fairness(test, test["fraud"].to_numpy(int), s_f, rules["fraud"]["rule_hs6_history"], tb)
    metrics["n_critical_test"] = int(test["critical"].sum())
    metrics["thresholds"] = th
    unc = res["fraud"]["uncertain"]
    y_f = test["fraud"].to_numpy(int)
    _t("metrics computed", t0)

    # ---- explanations + waterfalls (primary model) -----------------------------------------------------------
    reasons, waterfalls = {}, {}
    for target in C.TARGETS:
        twin = res[target]["twin"]
        G, base, top_inter = twin.contributions(res[target]["X_te"])
        reasons[target] = explain_frame(twin.lgbm, test, context, contrib=(G, base, top_inter))
        waterfalls[target] = [waterfall(G[i], base[i], twin.primary, target) for i in range(len(test))]
    _t("reasons + waterfalls for every TEST row", t0)
    ts = build_test_scored(test, res, rules, reasons, waterfalls)
    rd = R.prepare(ts, alert_thr=th["alert_threshold"])
    lanes_nounc = R.lanes_for(R.prepare(ts.drop(columns=["uncertain"]), alert_thr=th["alert_threshold"]), C.DEFAULT_RATE, 0.0)
    lanes = R.lanes_for(rd, C.DEFAULT_RATE, 0.0)
    ts["lane"] = lanes["lane"].astype(str)
    ts["alert"] = lanes["alert"]
    ts["rule_selected"] = lanes["rule_selected"]
    ts.to_parquet(C.ARTIFACTS / "test_scored.parquet", index=False)
    moved = (lanes_nounc["lane"] == "GREEN") & (lanes["lane"] == "YELLOW")
    metrics["uncertainty"] = {
        "threshold": d_thr, "n_flagged": int(unc.sum()), "share_flagged": float(unc.mean()),
        "fraud_rate_flagged": float(y_f[unc].mean()) if unc.any() else None,
        "fraud_rate_all": float(y_f.mean()),
        "green_to_yellow": int(moved.sum()),
        "fraud_rate_green_to_yellow": float(y_f[moved].mean()) if moved.any() else None,
        "fraud_rate_green_after": float(y_f[lanes["lane"] == "GREEN"].mean()),
        "shadow": {"late_period": sh["late_period"], "n_late": sh["n_late"]},
    }

    # ---- replay ---------------------------------------------------------------------------------------------
    runs = {f"{e:.1f}": R.replay(rd, rate=C.DEFAULT_RATE, explore=e) for e in (0.0, C.DEFAULT_EXPLORE)}
    (C.ARTIFACTS / "replay_default.json").write_text(json.dumps({"runs": runs}), encoding="utf-8")
    main_run = runs[f"{C.DEFAULT_EXPLORE:.1f}"]
    metrics["replay_summary"] = {
        "rate": C.DEFAULT_RATE, "explore": C.DEFAULT_EXPLORE,
        "totals": main_run["totals"], "n_days": main_run["n_days"],
        "policies": {p: {"label": v["label"], **v["summary"]} for p, v in main_run["policies"].items()},
    }
    _t("test_scored.parquet + replay_default.json written", t0)

    # ---- v2 analyses -----------------------------------------------------------------------------------------
    eff = EF.compute(rd)
    (C.ARTIFACTS / "efficiency.json").write_text(json.dumps(eff, indent=2), encoding="utf-8")
    metrics["efficiency"] = {k: eff[k] for k in ("matching", "pooled", "threats", "officer_hours")}
    exps = EX.run(train, test, res["fraud"]["X_tr"], res["fraud"]["X_te"], m_lgbm, m_ebm, metrics["uncertainty"], tb)
    (C.ARTIFACTS / "experiments.json").write_text(json.dumps(exps, indent=2), encoding="utf-8")
    xg = {"primary_model": primary,
          "targets": {t: XAI.global_view(res[t]["twin"].ebm, float(train[t].mean())) for t in C.TARGETS}}
    (C.ARTIFACTS / "xai_global.json").write_text(json.dumps(xg), encoding="utf-8")
    (C.ARTIFACTS / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    _t("efficiency, experiments, xai_global written", t0)

    # ---- console report --------------------------------------------------------------------------------------
    print("\n".join(E.metric_rows(metrics)))
    for target in C.TARGETS:
        ml, me = m_lgbm[target], m_ebm[target]
        g = metrics["targets"][target]["gain_vs_rule"]
        print(f"  {target}: LightGBM AUC {ml['auc']:.4f} P@5 {ml['precision_at_5']:.4f} R@5 {ml['recall_at_5']:.4f} | "
              f"EBM AUC {me['auc']:.4f} P@5 {me['precision_at_5']:.4f} R@5 {me['recall_at_5']:.4f} -> primary {primary[target]}")
        print(f"  gain AI - rule ({target}, {g['metric']}): {g['mean_gain']:+.3f} [95% CI {g['ci95'][0]:+.3f}, {g['ci95'][1]:+.3f}]")
    u = metrics["uncertainty"]
    print(f"  uncertain: {u['n_flagged']} flagged ({u['share_flagged']:.1%}), fraud rate {u['fraud_rate_flagged']:.3f}; "
          f"{u['green_to_yellow']} moved GREEN->YELLOW (fraud rate {u['fraud_rate_green_to_yellow']})")
    mt, pl = eff["matching"], eff["pooled"]
    print(f"  efficiency: rule@5% {mt['reference']['frauds']} frauds / {mt['reference']['inspections']} insp.; "
          f"AI@{mt.get('ai_rate')} {mt.get('ai_frauds')} / {mt.get('ai_inspections')} -> {mt.get('fewer_pct', 0):.1%} fewer; "
          f"pooled {pl['k_ai_needed']} vs {pl['k_rule']} -> {pl['fewer_pct']:.1%} fewer")
    for e in exps["experiments"]:
        print(f"  experiment {e['key']}: {e['decision']} {json.dumps(e['result'])[:160]}")
    print("\n".join(R.summary_table(main_run)))
    try:  # keep README numbers and docs/*.md in sync with the artifacts
        from . import report
        report.main()
    except Exception as exc:  # noqa: BLE001 - docs must never break the build
        print(f"[build] WARNING: report generation failed: {exc}")
    print(f"\n[build] done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
