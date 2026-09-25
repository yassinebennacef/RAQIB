"""Score a NEW declaration with the saved full-TRAIN encoding tables and models."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C
from .data import hs_description, hs6_str
from .engine import Engine, get_engine
from .explain import explain_frame, new_operator_notes

NEW_ID = "__NEW__"


def _clean_id(v) -> str:
    s = "" if v is None else str(v).strip()
    return s or NEW_ID


def to_frame(decl: dict) -> pd.DataFrame:
    hs6 = int(str(decl.get("hs6", "")).strip())
    mass = float(decl.get("net_mass", 0) or 0)
    price = float(decl.get("item_price", 0) or 0)
    row = {
        "HS6 Code": hs6,
        "hs4": hs6 // 100,
        "hs2": hs6 // 10000,
        "Importer ID": _clean_id(decl.get("importer_id")),
        "Declarant ID": _clean_id(decl.get("declarant_id")),
        "Seller ID": _clean_id(decl.get("seller_id")),
        "Country of Origin": str(decl.get("origin", "") or "").strip().upper() or NEW_ID,
        "Office ID": int(decl.get("office", 0) or 0),
        "Mode of Transport": int(decl.get("transport", 0) or 0),
        "Tax Rate": float(decl.get("tax_rate", 0) or 0),
        "Net Mass": mass,
        "Item Price": price,
        "unit": float(np.log1p(price / max(mass, 0.1))),
    }
    return pd.DataFrame([row])


def lane_for(engine: Engine, raw_fraud: float, raw_crit: float) -> tuple[str, str]:
    th = engine.thresholds
    if raw_crit >= th["alert_threshold"]:
        return "RED", "Public-safety alert: critical-fraud risk in the top 1% of the reference period."
    if raw_fraud >= th["red_threshold"]:
        return "RED", "Duty-fraud risk in the top 5% (the daily inspection capacity)."
    if raw_fraud >= th["yellow_threshold"]:
        return "YELLOW", "Duty-fraud risk in the next 10%: document check."
    return "GREEN", "Risk below the document-check threshold: release."


def score_new(decl: dict, engine: Engine | None = None) -> dict:
    engine = engine or get_engine()
    df = to_frame(decl)
    out: dict = {}
    for target, tm in engine.models.items():
        X = tm.features(df)
        raw = float(tm.raw(X)[0])
        out[target] = {
            "raw": raw,
            "p": float(tm.calibrate(np.array([raw]))[0]),
            "percentile": engine.percentile(target, raw),
            "reasons": explain_frame(tm, df, engine.context, X=X)[0],
        }
    lane, lane_reason = lane_for(engine, out["fraud"]["raw"], out["critical"]["raw"])
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
        "p_fraud": out["fraud"]["p"],
        "p_critical": out["critical"]["p"],
        "fraud_percentile": out["fraud"]["percentile"],
        "critical_percentile": out["critical"]["percentile"],
        "alert": bool(out["critical"]["raw"] >= engine.thresholds["alert_threshold"]),
        "lane": lane,
        "lane_reason": lane_reason,
        "reasons_fraud": out["fraud"]["reasons"],
        "reasons_critical": out["critical"]["reasons"][:2],
        "notes": notes,
        "thresholds": {
            "red_p_fraud": engine.thresholds["red_p_fraud"],
            "yellow_p_fraud": engine.thresholds["yellow_p_fraud"],
            "alert_p_critical": engine.thresholds["alert_p_critical"],
        },
        "transport_used_by_model": False,
    }
