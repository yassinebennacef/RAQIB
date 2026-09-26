"""Score a declaration (new, from the test set, or modified for a what-if) with the saved models.

Uses the full-TRAIN encoding tables, both twins (LightGBM + EBM), the primary model's exact
contributions (reasons + waterfall) and the lane policy (alerts, capacity thresholds, uncertainty).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config as C
from .data import hs_description, hs6_str
from .engine import Engine, get_engine
from .explain import GROUP_KEYS, GROUP_LABELS, explain_frame, new_operator_notes, waterfall

NEW_ID = "__NEW__"


def _clean_id(v) -> str:
    s = "" if v is None or (isinstance(v, float) and math.isnan(v)) else str(v).strip()
    return s or NEW_ID


def _row(hs6: int, importer, declarant, seller, origin: str, office: int, transport: int,
         tax: float, mass: float, price: float) -> dict:
    return {
        "HS6 Code": int(hs6), "hs4": int(hs6) // 100, "hs2": int(hs6) // 10000,
        "Importer ID": importer, "Declarant ID": declarant, "Seller ID": seller,
        "Country of Origin": origin, "Office ID": int(office), "Mode of Transport": int(transport),
        "Tax Rate": float(tax), "Net Mass": float(mass), "Item Price": float(price),
        "unit": float(np.log1p(float(price) / max(float(mass), 0.1))),
    }


def to_frame(decl: dict) -> pd.DataFrame:
    """Form declaration -> model input frame (empty operator = new operator)."""
    return pd.DataFrame([_row(
        int(str(decl.get("hs6", "")).strip()),
        _clean_id(decl.get("importer_id")), _clean_id(decl.get("declarant_id")), _clean_id(decl.get("seller_id")),
        str(decl.get("origin", "") or "").strip().upper() or NEW_ID,
        int(decl.get("office", 0) or 0), int(decl.get("transport", 0) or 0),
        float(decl.get("tax_rate", 0) or 0), float(decl.get("net_mass", 0) or 0), float(decl.get("item_price", 0) or 0),
    )])


def frame_from_test_row(r: pd.Series) -> pd.DataFrame:
    """test_scored row -> model input frame (a missing seller stays missing, as in the build)."""
    seller = r["seller"] if isinstance(r["seller"], str) and r["seller"].strip() else np.nan
    return pd.DataFrame([_row(int(r["hs6"]), r["importer"], r["declarant"], seller, r["origin"], int(r["office"]),
                              int(r["transport"]), float(r["tax_rate"]), float(r["net_mass"]), float(r["item_price"]))])


def apply_changes(df: pd.DataFrame, changes: dict) -> tuple[pd.DataFrame, list[str]]:
    """What-if: return a modified copy of a one-row frame and the list of changed fields."""
    d = df.iloc[0].to_dict()
    changed = []
    for k in ("item_price", "net_mass", "tax_rate"):
        if changes.get(k) is not None:
            d[{"item_price": "Item Price", "net_mass": "Net Mass", "tax_rate": "Tax Rate"}[k]] = float(changes[k])
            changed.append(k)
    if changes.get("origin"):
        d["Country of Origin"] = str(changes["origin"]).strip().upper()
        changed.append("origin")
    if changes.get("hs6"):
        h = int(str(changes["hs6"]).strip())
        d["HS6 Code"], d["hs4"], d["hs2"] = h, h // 100, h // 10000
        changed.append("hs6")
    for k, col in (("importer", "Importer ID"), ("declarant", "Declarant ID"), ("seller", "Seller ID")):
        v = changes.get(k)
        if v is not None and str(v).strip() != "":
            d[col] = NEW_ID if str(v).strip().lower() == "new" else str(v).strip().upper()
            changed.append(k)
    d["unit"] = float(np.log1p(d["Item Price"] / max(d["Net Mass"], 0.1)))
    return pd.DataFrame([d]), changed


def lane_for(engine: Engine, s_fraud: float, s_crit: float, uncertain: bool) -> tuple[str, str]:
    th = engine.thresholds
    if s_crit >= th["alert_threshold"]:
        return "RED", "Public-safety alert: critical-fraud risk in the top 1% of the reference period."
    if s_fraud >= th["red_threshold"]:
        return "RED", "Duty-fraud risk in the top 5% (the daily inspection capacity)."
    if s_fraud >= th["yellow_threshold"]:
        return "YELLOW", "Duty-fraud risk in the next 10%: document check."
    if uncertain:
        return "YELLOW", "The glass-box and black-box models disagree: human review (never released green)."
    return "GREEN", "Risk below the document-check threshold: release."


def score_frame(engine: Engine, df: pd.DataFrame) -> dict:
    """Full scoring of a one-row model input frame."""
    out: dict = {}
    for target, twin in engine.twins.items():
        X = twin.features(df)
        pred = twin.predict(X)
        G, base, top_inter = twin.contributions(X)
        out[target] = {
            "score": float(pred["score"][0]), "p": float(pred["p"][0]),
            "lgbm_p": float(pred["lgbm_p"][0]), "lgbm_raw": float(pred["lgbm_raw"][0]),
            "ebm_p": float(pred["ebm_p"][0]),
            "percentile": engine.percentile(target, float(pred["score"][0])),
            "reasons": explain_frame(twin.lgbm, df, engine.context, contrib=(G, base, top_inter))[0],
            "waterfall": waterfall(G[0], base[0], twin.primary, target),
            "G": G[0],
        }
    f = out["fraud"]
    disagreement = abs(f["ebm_p"] - f["lgbm_raw"]) if not math.isnan(f["ebm_p"]) else 0.0
    uncertain = bool(disagreement > engine.thresholds.get("disagreement_threshold", 1.0))
    lane, lane_reason = lane_for(engine, f["score"], out["critical"]["score"], uncertain)
    out["summary"] = {
        "p_fraud": f["p"], "p_critical": out["critical"]["p"],
        "fraud_percentile": f["percentile"], "critical_percentile": out["critical"]["percentile"],
        "alert": bool(out["critical"]["score"] >= engine.thresholds["alert_threshold"]),
        "lane": lane, "lane_reason": lane_reason,
        "uncertain": uncertain, "disagreement": float(disagreement),
        "models": {
            "primary": {t: tw.primary for t, tw in engine.twins.items()},
            "lightgbm": {"p_fraud": f["lgbm_p"], "p_critical": out["critical"]["lgbm_p"]},
            "ebm": {"p_fraud": f["ebm_p"], "p_critical": out["critical"]["ebm_p"]},
        },
        "waterfall": f["waterfall"], "waterfall_critical": out["critical"]["waterfall"],
        "reasons_fraud": f["reasons"], "reasons_critical": out["critical"]["reasons"][:2],
    }
    return out


def score_new(decl: dict, engine: Engine | None = None) -> dict:
    engine = engine or get_engine()
    df = to_frame(decl)
    res = score_frame(engine, df)
    notes = new_operator_notes(engine.models["fraud"], df)[0]
    row = df.iloc[0]
    return {
        "input": {
            "hs6": hs6_str(row["HS6 Code"]),
            "hs_description": hs_description(row["HS6 Code"]),
            "origin": row["Country of Origin"] if row["Country of Origin"] != NEW_ID else "",
            "office": int(row["Office ID"]),
            "office_label": C.office_label(row["Office ID"]),
            "transport": int(row["Mode of Transport"]),
            "transport_label": C.transport_label(row["Mode of Transport"]),
            "importer_id": "" if row["Importer ID"] == NEW_ID else row["Importer ID"],
            "declarant_id": "" if row["Declarant ID"] == NEW_ID else row["Declarant ID"],
            "seller_id": "" if row["Seller ID"] == NEW_ID else row["Seller ID"],
            "tax_rate": float(row["Tax Rate"]),
            "net_mass": float(row["Net Mass"]),
            "item_price": float(row["Item Price"]),
        },
        **res["summary"],
        "notes": notes,
        "thresholds": {
            "red_p_fraud": engine.thresholds["red_p_fraud"],
            "yellow_p_fraud": engine.thresholds["yellow_p_fraud"],
            "alert_p_critical": engine.thresholds["alert_p_critical"],
        },
        "transport_used_by_model": False,
    }


def whatif(engine: Engine, df_before: pd.DataFrame, changes: dict) -> dict:
    df_after, changed = apply_changes(df_before, changes)
    b, a = score_frame(engine, df_before), score_frame(engine, df_after)

    def side(r: dict) -> dict:
        s = r["summary"]
        return {k: s[k] for k in ("p_fraud", "p_critical", "lane", "lane_reason", "alert", "uncertain", "disagreement",
                                  "waterfall", "reasons_fraud")}

    gb, ga = b["fraud"]["G"], a["fraud"]["G"]
    deltas = [{"group": g, "label": GROUP_LABELS[g], "before": round(float(gb[i]), 4), "after": round(float(ga[i]), 4),
               "delta": round(float(ga[i] - gb[i]), 4)} for i, g in enumerate(GROUP_KEYS) if abs(ga[i] - gb[i]) > 1e-6]
    deltas.sort(key=lambda x: -abs(x["delta"]))
    return {"before": side(b), "after": side(a), "deltas": deltas, "changed": changed,
            "note": "Officer-only simulation tool; never shown to traders."}
