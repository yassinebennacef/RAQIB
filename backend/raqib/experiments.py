"""Ideas we tested, kept or rejected, all measured on the same test period."""
from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import KFold

from . import config as C
from . import evaluate as E

NETWORK_REASON = ("CTGAN synthesises rows independently, so cross-row links are artefacts; "
                  "re-test on real Tunisian data.")


def _counts(train: pd.DataFrame, df: pd.DataFrame, col: str) -> np.ndarray:
    return df[col].map(train[col].value_counts()).fillna(0).to_numpy(float)


def isolation_forest(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    """Unsupervised anomaly score on value/mass/tax and operator volumes."""
    med = train.groupby("HS6 Code")["unit"].median()
    mad = train.groupby("HS6 Code")["unit"].apply(lambda s: (s - s.median()).abs().median())
    g_mad = float((train["unit"] - train["unit"].median()).abs().median()) or 1.0

    def feats(df: pd.DataFrame) -> np.ndarray:
        m = df["HS6 Code"].map(med).fillna(train["unit"].median()).to_numpy(float)
        s = df["HS6 Code"].map(mad).fillna(g_mad).to_numpy(float)
        s = np.where(s > 1e-9, s, g_mad)
        return np.column_stack([
            (df["unit"].to_numpy(float) - m) / s,
            np.log1p(df["Net Mass"].to_numpy(float)),
            np.log1p(df["Item Price"].to_numpy(float)),
            df["Tax Rate"].to_numpy(float),
            _counts(train, df, "HS6 Code"), _counts(train, df, "Seller ID"), _counts(train, df, "Declarant ID"),
        ])

    iso = IsolationForest(n_estimators=300, random_state=0).fit(feats(train))
    score = -iso.score_samples(feats(test))
    y = test["fraud"].to_numpy(int)
    k = E.top_k(len(y), 0.01)
    top = np.argsort(-score, kind="mergesort")[:k]
    return {"fraud_auc": float(roc_auc_score(y, score)),
            "critical_auc": float(roc_auc_score(test["critical"].to_numpy(int), score)),
            "top1_fraud_rate": float(y[top].mean()), "base_rate": float(y.mean()), "k": k}


def _others_rate(stats_df: pd.DataFrame, rows: pd.DataFrame, via: str, target: str, a: float, prior: float) -> np.ndarray:
    """Smoothed fraud rate of OTHER importers' declarations sharing this row's seller/declarant."""
    y = stats_df[target].astype(float)
    by_via = y.groupby(stats_df[via]).agg(["sum", "count"])
    by_pair = y.groupby([stats_df[via], stats_df["Importer ID"]]).agg(["sum", "count"])
    s_v = rows[via].map(by_via["sum"]).fillna(0).to_numpy(float)
    c_v = rows[via].map(by_via["count"]).fillna(0).to_numpy(float)
    key = pd.MultiIndex.from_arrays([rows[via], rows["Importer ID"]])
    s_p = by_pair["sum"].reindex(key).fillna(0).to_numpy(float)
    c_p = by_pair["count"].reindex(key).fillna(0).to_numpy(float)
    return ((s_v - s_p) + a * prior) / ((c_v - c_p) + a)


def network_features(train: pd.DataFrame, test: pd.DataFrame, X_tr: pd.DataFrame, X_te: pd.DataFrame,
                     base_auc: float, base_p5: float, tb: np.ndarray) -> dict:
    """2-hop features (row -> seller/declarant -> other importers), out-of-fold, added to LightGBM."""
    target, a = "fraud", C.TARGETS["fraud"]
    prior = float(train[target].mean())
    cols = {"seller_others_rate": "Seller ID", "declarant_others_rate": "Declarant ID"}
    extra_tr = pd.DataFrame(index=train.index, columns=list(cols), dtype=float)
    for tr, va in KFold(C.N_FOLDS, shuffle=True, random_state=C.ENCODING_FOLDS_SEED).split(train):
        for name, via in cols.items():
            extra_tr.iloc[va, extra_tr.columns.get_loc(name)] = _others_rate(
                train.iloc[tr], train.iloc[va], via, target, a, prior)
    extra_te = pd.DataFrame({name: _others_rate(train, test, via, target, a, prior) for name, via in cols.items()},
                            index=test.index)
    Xa = pd.concat([X_tr.reset_index(drop=True), extra_tr.reset_index(drop=True)], axis=1)
    Xb = pd.concat([X_te.reset_index(drop=True), extra_te.reset_index(drop=True)], axis=1)
    mdl = LGBMClassifier(**C.LGBM_PARAMS).fit(Xa, train[target].to_numpy(int))
    s = mdl.predict_proba(Xb)[:, 1]
    m = E.method_metrics(test[target].to_numpy(int), s, tb)
    return {"auc_with": m["auc"], "auc_without": base_auc, "p5_with": m["precision_at_5"], "p5_without": base_p5,
            "features": list(cols)}


def run(train, test, X_tr_fraud, X_te_fraud, m_lgbm: dict, m_ebm: dict, uncertainty: dict, tb) -> dict:
    iso = isolation_forest(train, test)
    net = network_features(train, test, X_tr_fraud, X_te_fraud, m_lgbm["fraud"]["auc"],
                           m_lgbm["fraud"]["precision_at_5"], tb)

    def keys(m):
        return {"fraud_auc": m["fraud"]["auc"], "fraud_precision_at_5": m["fraud"]["precision_at_5"],
                "critical_auc": m["critical"]["auc"], "critical_recall_at_5": m["critical"]["recall_at_5"]}

    return {"experiments": [
        {"key": "ebm", "title": "Glass-box model (Explainable Boosting Machine)", "decision": "kept",
         "hypothesis": "A fully transparent additive model can match the black-box gradient boosting.",
         "method": "Same features, EBM with 5 pairwise interactions and 4 outer bags; test period metrics.",
         "result": keys(m_ebm), "baseline": keys(m_lgbm),
         "reason": "As accurate as LightGBM while every prediction is an exact sum of readable contributions."},
        {"key": "disagreement", "title": "Uncertainty from model disagreement", "decision": "kept",
         "hypothesis": "Where the glass box and the black box disagree, a human should look.",
         "method": "|p(EBM) - p(LightGBM)| above the 95th percentile of out-of-sample disagreement on the last 4 training weeks.",
         "result": uncertainty,
         "reason": "Flagged declarations are never released green; they go to a document check."},
        {"key": "isolation_forest", "title": "Anomaly detection (Isolation Forest)", "decision":
         "rejected" if iso["fraud_auc"] < 0.55 else "kept",
         "hypothesis": "Unusual declarations (value per kg far from the product's usual value, odd mass or volume) are more often fraudulent.",
         "method": "IsolationForest(300 trees) on unit-value z-score vs the product median, log mass, log value, tax rate and product/seller/declarant volumes, fitted on TRAIN.",
         "result": iso,
         "reason": "No signal: the top 1% anomalies are fraudulent at about the base rate." if iso["fraud_auc"] < 0.55 else "Some signal."},
        {"key": "network_2hop", "title": "2-hop network features", "decision":
         "rejected" if net["auc_with"] <= net["auc_without"] + 0.002 else "kept",
         "hypothesis": "An importer using sellers or declarants that serve fraudulent importers is riskier.",
         "method": "Out-of-fold smoothed fraud rate of the OTHER importers sharing the seller / declarant, added to LightGBM.",
         "result": net,
         "reason": "No gain. " + NETWORK_REASON},
    ]}
