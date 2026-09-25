"""Plain-English reasons from exact TreeSHAP contributions.

LightGBM's booster.predict(X, pred_contrib=True) gives one additive contribution per
feature (log-odds). Contributions are grouped by concept, the 4 largest |groups| are
kept and each is written as a sentence with the real historical numbers.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .data import hs2_description, hs4_description, hs_description, hs6_str

# (group, label, features, source column, encoder short name)
GROUPS: list[tuple[str, str, list[str], str | None, str | None]] = [
    ("product", "Product (HS6) history", ["rate_hs6", "count_hs6"], "HS6 Code", "hs6"),
    ("family", "Product family (HS4)", ["rate_hs4", "count_hs4"], "hs4", "hs4"),
    ("chapter", "HS chapter", ["rate_hs2", "count_hs2"], "hs2", "hs2"),
    ("importer", "Importer history", ["rate_importer", "count_importer"], "Importer ID", "importer"),
    ("declarant", "Declarant history", ["rate_declarant", "count_declarant"], "Declarant ID", "declarant"),
    ("seller", "Seller history", ["rate_seller", "count_seller"], "Seller ID", "seller"),
    ("origin", "Country of origin", ["rate_origin", "count_origin"], "Country of Origin", "origin"),
    ("office", "Customs office", ["rate_office", "count_office"], "Office ID", "office"),
    ("tax", "Tax rate", ["tax_rate"], None, None),
    ("value", "Value and mass", ["net_mass", "item_price", "unit"], None, None),
]
GROUP_DEFS = [(g, label, feats) for g, label, feats, _, _ in GROUPS]
GROUP_LABELS = {g: label for g, label, *_ in GROUPS}
NEW_ROLE = {"importer": "importer", "declarant": "declarant", "seller": "seller"}


def group_contributions(tm, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    contrib = tm.model.booster_.predict(X, pred_contrib=True)
    idx = {f: i for i, f in enumerate(C.FEATURES)}
    G = np.stack([contrib[:, [idx[f] for f in feats]].sum(axis=1) for _, _, feats, _, _ in GROUPS], axis=1)
    return G, contrib[:, -1]


def _short(text: str, n: int = 58) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1].rstrip(" ,;") + "…"


def fmt_rate(r: float, target: str) -> str:
    return f"{r * 100:.1f}%" if target == "critical" else f"{r * 100:.0f}%"


def fmt_num(x: float) -> str:
    x = float(x)
    if abs(x) >= 1e9:
        return f"{x / 1e9:.1f}B"
    if abs(x) >= 1e6:
        return f"{x / 1e6:.1f}M"
    if abs(x) >= 100:
        return f"{x:,.0f}"
    if abs(x) >= 1:
        return f"{x:,.1f}"
    return f"{x:.2f}"


class RowContext:
    """Vectorised per-row facts needed to write sentences."""

    def __init__(self, tm, df: pd.DataFrame, context: dict):
        self.tm = tm
        self.target = tm.target
        self.prior = tm.prior
        self.stats = {}
        for g, _, _, col, name in GROUPS:
            if col:
                self.stats[g] = tm.encoder.stats(df, col, name)
        self.values = {col: df[col].to_numpy() for _, _, _, col, _ in GROUPS if col}
        self.tax = df["Tax Rate"].to_numpy(dtype=float)
        self.mass = df["Net Mass"].to_numpy(dtype=float)
        self.price = df["Item Price"].to_numpy(dtype=float)
        med = context.get("hs6_unit_median") if context else None
        self.unit_med = df["HS6 Code"].map(med).to_numpy(dtype=float) if med is not None else np.full(len(df), np.nan)


def sentence(g: str, i: int, rc: RowContext) -> tuple[str, bool]:
    """Return (text, thin_history) for group g of row i."""
    target = rc.target
    what = "fraud" if target == "fraud" else "critical violations"
    verb = "was fraudulent in" if target == "fraud" else "had a critical violation in"
    avg = fmt_rate(rc.prior, target)

    if g in rc.stats:
        s, c = rc.stats[g][0][i], rc.stats[g][1][i]
        n = int(c)
        rate = fmt_rate(s / c, target) if c > 0 else None
        col = next(col for gg, _, _, col, _ in GROUPS if gg == g)
        v = rc.values[col][i]
        thin = 0 < n < C.THIN_HISTORY
        suffix = " (thin history)" if thin else ""
        if g == "product":
            code = hs6_str(v)
            if n == 0:
                return f"Product {code} ({_short(hs_description(v))}): no history (treated as average risk).", False
            return f"Product {code} ({_short(hs_description(v))}) {verb} {rate} of its {n:,} past declarations (average {avg}){suffix}.", thin
        if g == "family":
            code = str(int(v)).zfill(4)
            if n == 0:
                return f"Product family {code}: no history (treated as average risk).", False
            return f"Product family {code} ({_short(hs4_description(v), 44)}): {rate} {what} on {n:,} past declarations{suffix}.", thin
        if g == "chapter":
            code = str(int(v)).zfill(2)
            if n == 0:
                return f"HS chapter {code}: no history (treated as average risk).", False
            return f"HS chapter {code} ({_short(hs2_description(v), 44)}): {rate} {what} on {n:,} past declarations{suffix}.", thin
        if g in NEW_ROLE:
            role = NEW_ROLE[g]
            if pd.isna(v) or str(v).strip() == "":
                return f"{role.capitalize()} not declared (treated as average risk).", False
            if n == 0:
                return f"New {role}: no history (treated as average risk).", False
            return f"{role.capitalize()} {v}: {rate} {what} on {n:,} past declarations (average {avg}){suffix}.", thin
        if g == "origin":
            if n == 0:
                return f"Origin {v}: no history (treated as average risk).", False
            return f"Origin {v}: {rate} {what} on {n:,} past declarations (average {avg}){suffix}.", thin
        if g == "office":
            if n == 0:
                return f"{C.office_label(v)}: no history (treated as average risk).", False
            return f"{C.office_label(v)}: {rate} {what} on {n:,} past declarations (average {avg}){suffix}.", thin

    if g == "tax":
        t = rc.tax[i]
        if t > 0:
            return f"Tax rate {t:g}%: duty at stake.", False
        return "Tax rate 0%: no duty at stake.", False

    # value / mass
    uv = rc.price[i] / max(rc.mass[i], 0.1)
    med = rc.unit_med[i]
    if np.isfinite(med) and med > 0:
        diff = uv / med - 1
        if abs(diff) < 0.01:
            cmp = "in line with this product's usual value"
        elif diff > 0:
            cmp = f"{diff * 100:,.0f}% above this product's usual {fmt_num(med)} KRW/kg"
        else:
            cmp = f"{-diff * 100:,.0f}% below this product's usual {fmt_num(med)} KRW/kg"
    else:
        cmp = "no reference value for this product"
    return f"Unit value {fmt_num(uv)} KRW/kg ({fmt_num(rc.price[i])} KRW for {fmt_num(rc.mass[i])} kg): {cmp}.", False


def explain_frame(tm, df: pd.DataFrame, context: dict, X: pd.DataFrame | None = None, top: int = 4) -> list[list[dict]]:
    """Top-`top` reasons for every row of df (rows scored with full-TRAIN statistics)."""
    if X is None:
        X = tm.features(df)
    G, _ = group_contributions(tm, X)
    rc = RowContext(tm, df, context)
    out = []
    for i in range(len(df)):
        order = np.argsort(-np.abs(G[i]), kind="mergesort")[:top]
        reasons = []
        for j in order:
            g = GROUPS[j][0]
            text, thin = sentence(g, i, rc)
            val = float(G[i, j])
            if g == "tax" and val < 0 and rc.tax[i] > 0:
                text = f"Tax rate {rc.tax[i]:g}%: little duty at stake."
            if g in rc.stats and rc.stats[g][1][i] > 0:
                hist = rc.stats[g][0][i] / rc.stats[g][1][i]
                # history below average but pushes risk up (or the reverse): say so honestly
                if (hist < rc.prior and val > 0) or (hist > rc.prior and val < 0):
                    text = text[:-1] + " (interaction with other factors)."
            reasons.append({
                "group": g,
                "label": GROUP_LABELS[g],
                "text": text,
                "contribution": round(val, 4),
                "direction": "raises" if val > 0 else "lowers",
                "thin_history": bool(thin),
            })
        out.append(reasons)
    return out


def new_operator_notes(tm, df: pd.DataFrame) -> list[list[str]]:
    """'New importer: no history' notes for every operator without history."""
    notes = [[] for _ in range(len(df))]
    for g in ("importer", "declarant", "seller"):
        col, name = next((col, name) for gg, _, _, col, name in GROUPS if gg == g)
        _, c = tm.encoder.stats(df, col, name)
        missing = df[col].isna().to_numpy()
        for i in np.where(c == 0)[0]:
            if missing[i]:
                notes[i].append(f"{g.capitalize()} not declared (treated as average risk).")
            else:
                notes[i].append(f"New {g}: no history (treated as average risk).")
    return notes
