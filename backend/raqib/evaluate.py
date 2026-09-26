"""Measured results on TEST (Apr-Jun 2021): AI vs rules vs random, for both targets.

Everything written to artifacts/metrics.json is computed here from the data.
Top-k selections use k = ceil(share x n); ties are broken by one fixed random
permutation of the TEST rows (seed 0), identical for every method.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from . import config as C

FRACS: list[tuple[float, str]] = [(0.01, "1"), (0.05, "5"), (0.10, "10")]
METHODS = ["ai", "rule_hs6_history", "rule_importer_history", "random"]
METHOD_LABELS = {
    "ai": "RAQIB AI",
    "rule_hs6_history": "Rule: product (HS6) history",
    "rule_importer_history": "Rule: importer history",
    "random": "Random selection",
}
TARGET_LABELS = {"fraud": "Duty fraud (revenue)", "critical": "Critical fraud (public safety)"}


def tiebreak_for(n: int, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).permutation(n).astype(float)


def order_desc(score, tiebreak) -> np.ndarray:
    return np.lexsort((np.asarray(tiebreak, float), -np.asarray(score, float)))


def top_k(n: int, frac: float) -> int:
    return max(1, int(np.ceil(frac * n)))


def method_metrics(y, score, tiebreak) -> dict:
    y = np.asarray(y, dtype=int)
    order = order_desc(score, tiebreak)
    pos = max(int(y.sum()), 1)
    m: dict = {"auc": float(roc_auc_score(y, score))}
    for frac, tag in FRACS:
        k = top_k(len(y), frac)
        tp = int(y[order[:k]].sum())
        p, r = tp / k, tp / pos
        m[f"precision_at_{tag}"] = p
        m[f"recall_at_{tag}"] = r
        m[f"caught_at_{tag}"] = tp
        m[f"k_at_{tag}"] = k
        # one standard error (binomial), so the UI can show the sampling noise
        m[f"precision_se_at_{tag}"] = float(np.sqrt(p * (1 - p) / k))
        m[f"recall_se_at_{tag}"] = float(np.sqrt(r * (1 - r) / pos))
    return m


def paired_gain_ci(y, s_ai, s_rule, tiebreak, frac=0.05, metric="precision", n_boot=500, seed=0) -> dict:
    """Bootstrap (rows resampled with replacement) of AI minus rule at top frac."""
    y = np.asarray(y, int)
    rng = np.random.default_rng(seed)
    n = len(y)
    k = top_k(n, frac)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        yb = y[idx]
        pos = max(int(yb.sum()), 1)
        vals = []
        for s in (s_ai, s_rule):
            o = order_desc(np.asarray(s)[idx], np.asarray(tiebreak)[idx])[:k]
            tp = yb[o].sum()
            vals.append(tp / k if metric == "precision" else tp / pos)
        diffs[b] = vals[0] - vals[1]
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"metric": f"{metric}_at_{int(frac * 100)}", "mean_gain": float(diffs.mean()),
            "ci95": [float(lo), float(hi)], "n_boot": n_boot,
            "share_boot_ai_better": float((diffs > 0).mean())}


def calibration_table(y, p_cal, raw, bins: int = 10) -> list[dict]:
    """10 equal-size bins by predicted risk: mean calibrated probability vs observed rate."""
    y = np.asarray(y, int)
    order = np.argsort(np.asarray(raw), kind="mergesort")
    rows = []
    for i, chunk in enumerate(np.array_split(order, bins)):
        rows.append({
            "bin": i + 1,
            "n": int(len(chunk)),
            "mean_predicted": float(np.mean(p_cal[chunk])),
            "observed": float(np.mean(y[chunk])),
        })
    return rows


def weekly_table(dates: pd.Series, y, scores: dict[str, np.ndarray], tiebreak, frac=0.05) -> list[dict]:
    y = np.asarray(y, int)
    d = pd.to_datetime(dates).reset_index(drop=True)
    week = ((d - d.min()).dt.days // 7).to_numpy()
    out = []
    for w in np.unique(week):
        idx = np.where(week == w)[0]
        k = top_k(len(idx), frac)
        pos = int(y[idx].sum())
        row = {
            "week": int(w) + 1,
            "start": str(d.iloc[idx].min().date()),
            "n": int(len(idx)),
            "positives": pos,
            "base_rate": float(y[idx].mean()),
        }
        for name, s in scores.items():
            o = idx[order_desc(np.asarray(s)[idx], np.asarray(tiebreak)[idx])[:k]]
            tp = int(y[o].sum())
            row[f"precision_{name}"] = tp / k
            row[f"recall_{name}"] = (tp / pos) if pos else None
        out.append(row)
    return out


def importance(tm, groups) -> dict:
    gain = tm.model.booster_.feature_importance(importance_type="gain").astype(float)
    share = gain / gain.sum() if gain.sum() > 0 else gain
    feats = [{"feature": f, "share": float(s)} for f, s in zip(C.FEATURES, share)]
    feats.sort(key=lambda r: -r["share"])
    idx = {f: i for i, f in enumerate(C.FEATURES)}
    grp = [{"group": g, "label": label, "share": float(sum(share[idx[f]] for f in fs))}
           for g, label, fs in groups]
    grp.sort(key=lambda r: -r["share"])
    return {"features": feats, "groups": grp}


def fairness(test: pd.DataFrame, y, s_ai, s_rule, tiebreak, frac=0.05, min_n=50) -> dict:
    """Selection rate by office and by transport mode for the AI top 5% vs the rule top 5%."""
    y = np.asarray(y, int)
    n = len(test)
    k = top_k(n, frac)
    sel = {}
    for name, s in (("ai", s_ai), ("rule", s_rule)):
        m = np.zeros(n, bool)
        m[order_desc(s, tiebreak)[:k]] = True
        sel[name] = m
    out = {"k": k, "share": frac}
    for key, col, labeler in (("office", "Office ID", C.office_label),
                              ("transport", "Mode of Transport", C.transport_label)):
        codes = test[col].to_numpy()
        counts = pd.Series(codes).value_counts()
        big = [c for c, v in counts.items() if v >= min_n]
        rows = []
        for code in big + ["__other__"]:
            mask = ~np.isin(codes, big) if code == "__other__" else codes == code
            if mask.sum() == 0:
                continue
            rows.append({
                "code": "other" if code == "__other__" else str(code),
                "label": f"Others (< {min_n} decl. each)" if code == "__other__" else labeler(code),
                "n": int(mask.sum()),
                "share_declarations": float(mask.mean()),
                "share_inspections_ai": float(sel["ai"][mask].sum() / k),
                "share_inspections_rule": float(sel["rule"][mask].sum() / k),
                "selection_rate_ai": float(sel["ai"][mask].mean()),
                "selection_rate_rule": float(sel["rule"][mask].mean()),
                "fraud_rate": float(y[mask].mean()),
            })
        rated = [r for r in rows if r["n"] >= 100 and r["selection_rate_ai"] > 0]
        ratio = (max(r["selection_rate_ai"] for r in rated) / min(r["selection_rate_ai"] for r in rated)) if len(rated) > 1 else None
        out[key] = {"rows": rows, "max_min_selection_ratio_ai": ratio}
    return out


def metric_rows(metrics: dict) -> list[str]:
    """Plain-text table for the console."""
    lines = []
    for target, t in metrics["targets"].items():
        lines.append(f"\n{TARGET_LABELS[target]}  (TEST positives: {t['n_positive']}, base rate {t['base_rate']:.3f})")
        lines.append(f"  {'method':30s} {'AUC':>6s} {'P@1%':>6s} {'P@5%':>6s} {'P@10%':>6s} {'R@1%':>6s} {'R@5%':>6s} {'R@10%':>6s}")
        for mname in METHODS:
            m = t["methods"][mname]
            lines.append(
                f"  {METHOD_LABELS[mname]:30s} {m['auc']:6.3f} {m['precision_at_1']:6.3f} {m['precision_at_5']:6.3f} "
                f"{m['precision_at_10']:6.3f} {m['recall_at_1']:6.3f} {m['recall_at_5']:6.3f} {m['recall_at_10']:6.3f}"
            )
    return lines


def ebm_importance(ebm) -> dict:
    """Mean absolute contribution of each EBM term (glass box), as shares, grouped by concept."""
    from .explain import FEATURE_GROUP, GROUP_LABELS

    imp = np.asarray(ebm.term_importances(), dtype=float)
    share = imp / imp.sum() if imp.sum() > 0 else imp
    names = list(ebm.term_names_)
    feats = sorted(({"feature": n, "share": float(v)} for n, v in zip(names, share)), key=lambda r: -r["share"])
    groups: dict[str, float] = {}
    for n, v in zip(names, share):
        if " & " in n:
            a, b = n.split(" & ")
            g = FEATURE_GROUP[a] if FEATURE_GROUP.get(a) == FEATURE_GROUP.get(b) else "interaction"
        else:
            g = FEATURE_GROUP[n]
        groups[g] = groups.get(g, 0.0) + float(v)
    grp = sorted(({"group": g, "label": GROUP_LABELS[g], "share": v} for g, v in groups.items()), key=lambda r: -r["share"])
    return {"features": feats, "groups": grp}
