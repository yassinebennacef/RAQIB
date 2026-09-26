"""Global glass-box view of the EBM: term importances and the learned shape functions."""
from __future__ import annotations

import numpy as np

from .explain import FEATURE_GROUP

TERM_LABELS = {
    "rate_hs6": "Past fraud rate of the product (HS6)", "count_hs6": "Past declarations of the product (HS6)",
    "rate_hs4": "Past fraud rate of the product family (HS4)", "count_hs4": "Past declarations of the product family",
    "rate_hs2": "Past fraud rate of the HS chapter", "count_hs2": "Past declarations of the HS chapter",
    "rate_importer": "Past fraud rate of the importer", "count_importer": "Past declarations of the importer",
    "rate_declarant": "Past fraud rate of the declarant", "count_declarant": "Past declarations of the declarant",
    "rate_seller": "Past fraud rate of the seller", "count_seller": "Past declarations of the seller",
    "rate_origin": "Past fraud rate of the origin country", "count_origin": "Past declarations from the origin",
    "rate_office": "Past fraud rate of the customs office", "count_office": "Past declarations at the office",
    "tax_rate": "Tax rate", "net_mass": "Net mass", "item_price": "Declared value", "unit": "Unit value",
}


def term_label(term: str) -> str:
    if " & " in term:
        a, b = term.split(" & ")
        return f"{TERM_LABELS.get(a, a)} × {TERM_LABELS.get(b, b)}"
    return TERM_LABELS.get(term, term)


def _x_axis(feature: str) -> tuple[str, float, str, callable]:
    """(axis label, scale, 'linear'|'log', transform) in natural units."""
    if feature.startswith("rate_"):
        what = TERM_LABELS[feature].replace("Past fraud rate of the ", "")
        return f"past fraud rate of the {what} (%)", 100.0, "linear", lambda v: v * 100.0
    if feature.startswith("count_"):
        return TERM_LABELS[feature].lower(), 1.0, "log", lambda v: v
    if feature == "tax_rate":
        return "tax rate (%)", 1.0, "linear", lambda v: v
    if feature == "net_mass":
        return "net mass (kg)", 1.0, "log", lambda v: v
    if feature == "item_price":
        return "declared value (KRW)", 1.0, "log", lambda v: v
    return "unit value (KRW per kg)", 1.0, "log", lambda v: np.expm1(v)


def shape(ebm, feature: str, max_points: int = 60) -> dict | None:
    names_in = list(ebm.feature_names_in_)
    terms = list(ebm.term_names_)
    if feature not in names_in or feature not in terms:
        return None
    fi, ti = names_in.index(feature), terms.index(feature)
    cuts = np.asarray(ebm.bins_[fi][0], dtype=float)
    scores = np.asarray(ebm.term_scores_[ti], dtype=float)
    sds = np.asarray(ebm.standard_deviations_[ti], dtype=float)
    lo, hi = (float(v) for v in ebm.feature_bounds_[fi])
    edges = np.concatenate([[lo], cuts, [hi]])
    centres = (edges[:-1] + edges[1:]) / 2.0
    y, sd = scores[1:-1], sds[1:-1]  # drop the 'missing' and 'unknown' bins
    n = min(len(centres), len(y))
    centres, y, sd = centres[:n], y[:n], sd[:n]
    if n > max_points:
        idx = np.unique(np.linspace(0, n - 1, max_points).round().astype(int))
        centres, y, sd = centres[idx], y[idx], sd[idx]
    x_label, _, scale, tf = _x_axis(feature)
    xs = tf(centres)
    return {"term": feature, "label": TERM_LABELS.get(feature, feature), "group": FEATURE_GROUP.get(feature),
            "x_label": x_label, "x_scale": scale, "y_label": "effect on risk (log-odds)",
            "points": [{"x": float(a), "y": float(b), "lower": float(b - s), "upper": float(b + s)}
                       for a, b, s in zip(xs, y, sd)]}


def global_view(ebm, base_rate: float, top_shapes: int = 8) -> dict:
    imp = np.asarray(ebm.term_importances(), dtype=float)
    total = float(imp.sum()) or 1.0
    terms = list(ebm.term_names_)
    rows = sorted(({"term": t, "label": term_label(t),
                    "group": "interaction" if " & " in t else FEATURE_GROUP.get(t),
                    "importance": float(v), "share": float(v) / total} for t, v in zip(terms, imp)),
                  key=lambda r: -r["importance"])
    mains = [r["term"] for r in rows if " & " not in r["term"]][:top_shapes]
    shapes = [s for s in (shape(ebm, t) for t in mains) if s]
    return {"model": "ebm", "intercept": float(np.ravel(ebm.intercept_)[0]), "base_rate": base_rate,
            "importances": rows, "shapes": shapes}
