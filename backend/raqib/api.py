"""RAQIB HTTP API (FastAPI). Shapes are documented in API.md.

Run with `python -m raqib.serve`. When frontend/dist exists it is served at / (SPA).
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from contextlib import asynccontextmanager
from typing import Any, Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config as C
from . import decisions as D
from .data import hs_description, hs_table, load_train
from .engine import Engine, artifacts_status, get_engine
from .score import score_new

@asynccontextmanager
async def lifespan(_app):
    import time
    t0 = time.time()
    try:
        get_engine()
        train_index()
        _presets()
        print(f"[raqib] artifacts loaded in {time.time() - t0:.1f}s", flush=True)
    except Exception as exc:  # noqa: BLE001 - the API still answers /api/health
        print(f"[raqib] WARNING: artifacts not loaded ({exc}). Run: python -m raqib.build", flush=True)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="RAQIB API",
    version="0.9",
    description="AI targeting of customs import declarations under a fixed inspection capacity. "
                "Advisory only: the officer decides.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------- helpers
def py(obj: Any) -> Any:
    """Recursively convert numpy / pandas values to JSON-safe Python values."""
    if isinstance(obj, dict):
        return {str(k): py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [py(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [py(v) for v in obj.tolist()]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return None if math.isnan(f) or math.isinf(f) else f
    if obj is pd.NA or obj is None:
        return None
    return obj


def engine() -> Engine:
    try:
        return get_engine()
    except FileNotFoundError as exc:
        raise HTTPException(503, f"Artifacts missing ({exc.filename}). Run: python -m raqib.build") from exc


@lru_cache(maxsize=1)
def train_index() -> dict:
    """Past (TRAIN) relations used for operator history and the small network."""
    tr = load_train()
    pairs = {}
    for role, col in (("declarant", "Declarant ID"), ("seller", "Seller ID")):
        g = tr.groupby([col, "Importer ID"]).size().rename("n").reset_index()
        pairs[role] = {k: v.sort_values("n", ascending=False) for k, v in g.groupby(col)}
    stats = {}
    for role, col in (("importer", "Importer ID"), ("declarant", "Declarant ID"), ("seller", "Seller ID")):
        stats[role] = tr.groupby(col).agg(n=("fraud", "size"), frauds=("fraud", "sum"),
                                          criticals=("critical", "sum"))
    hs6_seen = tr["HS6 Code"].value_counts()
    return {"pairs": pairs, "stats": stats, "hs6_seen": hs6_seen,
            "prior_fraud": float(tr["fraud"].mean()), "prior_critical": float(tr["critical"].mean())}


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA or str(v).strip() == ""


def operator_history(role: str, op_id) -> dict:
    s = train_index()["stats"][role]
    if _missing(op_id):
        return {"id": None, "role": role, "past_declarations": 0, "is_new": True, "missing": True,
                "fraud_rate": None, "critical_rate": None, "thin_history": True}
    if op_id in s.index:
        r = s.loc[op_id]
        n = int(r["n"])
        return {"id": op_id, "role": role, "past_declarations": n, "is_new": False, "missing": False,
                "fraud_rate": float(r["frauds"] / n), "critical_rate": float(r["criticals"] / n),
                "thin_history": n < C.THIN_HISTORY}
    return {"id": op_id, "role": role, "past_declarations": 0, "is_new": True, "missing": False,
            "fraud_rate": None, "critical_rate": None, "thin_history": True}


def small_network(declarant: str, seller: str, importer: str, max_nodes: int = 25) -> dict:
    idx = train_index()
    nodes: dict[str, dict] = {}
    links: list[dict] = []

    def importer_node(imp: str, focus: bool = False) -> str:
        key = f"importer:{imp}"
        if key not in nodes:
            h = operator_history("importer", imp)
            nodes[key] = {"id": key, "type": "importer", "label": imp, "is_focus": focus,
                          "past_declarations": h["past_declarations"], "fraud_rate": h["fraud_rate"]}
        return key

    hubs = [(r, o) for r, o in (("declarant", declarant), ("seller", seller)) if not _missing(o)]
    for role, op in hubs:
        h = operator_history(role, op)
        nodes[f"{role}:{op}"] = {"id": f"{role}:{op}", "type": role, "label": op, "is_focus": False,
                                 "past_declarations": h["past_declarations"], "fraud_rate": h["fraud_rate"]}
    focus = importer_node(importer, focus=True)
    budget = max_nodes - len(nodes)
    per_role = max(budget // max(len(hubs), 1), 0)
    for role, op in hubs:
        src = f"{role}:{op}"
        df = idx["pairs"][role].get(op)
        links_added = 0
        if df is not None:
            for imp, n in zip(df["Importer ID"], df["n"]):
                if imp == importer:
                    links.append({"source": src, "target": focus, "past_declarations": int(n)})
                    continue
                if links_added >= per_role or len(nodes) >= max_nodes:
                    continue
                key = importer_node(imp)
                links.append({"source": src, "target": key, "past_declarations": int(n)})
                links_added += 1
        if not any(l["source"] == src and l["target"] == focus for l in links):
            links.append({"source": src, "target": focus, "past_declarations": 0})
    return {"nodes": list(nodes.values()), "links": links,
            "note": "Past relations (TRAIN period). Fraud rate = share of an importer's past declarations found fraudulent."}


def reasons_of(row: pd.Series) -> tuple[list, list]:
    return json.loads(row["reasons_fraud"]), json.loads(row["reasons_critical"])


def lane_reason(lane: str, alert: bool, explored: bool) -> str:
    if lane == "RED" and alert:
        return "Public-safety alert: critical-fraud risk in the top 1% - takes an inspection slot first."
    if lane == "RED" and explored:
        return "Exploration pick: random inspection so the system never goes blind."
    if lane == "RED":
        return "Within today's inspection capacity by duty-fraud risk."
    if lane == "YELLOW":
        return "Next 10% of today's risk: document check."
    return "Below today's thresholds: release."


def _check_rate(rate: float, explore: float) -> None:
    if not (0.005 <= rate <= 0.5):
        raise HTTPException(422, "rate must be between 0.005 and 0.5")
    if not (0.0 <= explore <= 0.5):
        raise HTTPException(422, "explore must be between 0 and 0.5")


# ---------------------------------------------------------------------------- models
class ScoreRequest(BaseModel):
    hs6: str = Field(..., description="6-digit HS code, e.g. 621149")
    origin: str = Field("", description="ISO alpha-2 country of origin")
    office: int = 40
    importer_id: str | None = ""
    declarant_id: str | None = ""
    seller_id: str | None = ""
    tax_rate: float = 8.0
    net_mass: float = 1.0
    item_price: float = 1.0
    transport: int = 40


class DecisionRequest(BaseModel):
    declaration_id: str
    decision: Literal["INSPECT", "DOCUMENT_CHECK", "RELEASE"]
    comment: str = ""
    officer: str = "Officer"


# ---------------------------------------------------------------------------- endpoints
@app.get("/api/health")
def health() -> dict:
    status = artifacts_status()
    loaded, err = False, None
    try:
        e = get_engine()
        loaded = True
        n_test, n_days = len(e.test), len(e.rd.dates)
    except Exception as exc:  # noqa: BLE001 - report, never crash
        err, n_test, n_days = str(exc), 0, 0
    return {"status": "ok" if loaded else "degraded", "models_loaded": loaded, "artifacts": status,
            "n_test_declarations": n_test, "n_days": n_days, "error": err,
            "frontend_built": (C.FRONTEND_DIST / "index.html").exists()}


@app.get("/api/data-card")
def data_card() -> dict:
    return engine().data_card


@app.get("/api/metrics")
def metrics() -> dict:
    return engine().metrics


@app.get("/api/replay")
def replay(rate: float = C.DEFAULT_RATE, explore: float = C.DEFAULT_EXPLORE) -> dict:
    _check_rate(rate, explore)
    return py(engine().replay(rate, explore))


@app.get("/api/stream")
def stream(day: int = 0, rate: float = C.DEFAULT_RATE, explore: float = 0.0) -> dict:
    _check_rate(rate, explore)
    e = engine()
    if not (0 <= day < len(e.rd.dates)):
        raise HTTPException(404, f"day must be between 0 and {len(e.rd.dates) - 1}")
    lanes = e.lanes(rate, explore)
    idx = e.rd.day_rows[day]
    sub = e.test.iloc[idx]
    order = np.argsort(-sub["score_fraud"].to_numpy(), kind="mergesort")
    rank = np.empty(len(idx), int)
    rank[order] = np.arange(1, len(idx) + 1)
    cols = {c: sub[c].tolist() for c in ("declaration_id", "hs6", "hs_desc", "origin", "office_label",
                                         "transport_label", "item_price", "net_mass", "p_fraud",
                                         "p_critical", "top_reason", "fraud", "critical")}
    lane_l, alert_l = lanes["lane"][idx].tolist(), lanes["alert"][idx].tolist()
    expl_l, rule_l = lanes["explored"][idx].tolist(), lanes["rule_selected"][idx].tolist()
    items = [{
        "id": cols["declaration_id"][j],
        "hs6": str(int(cols["hs6"][j])).zfill(6),
        "hs_desc": cols["hs_desc"][j],
        "origin": cols["origin"][j],
        "office_label": cols["office_label"][j],
        "transport_label": cols["transport_label"][j],
        "item_price": float(cols["item_price"][j]),
        "net_mass": float(cols["net_mass"][j]),
        "lane": str(lane_l[j]),
        "alert": bool(alert_l[j]),
        "explored": bool(expl_l[j]),
        "rule_selected": bool(rule_l[j]),
        "p_fraud": float(cols["p_fraud"][j]),
        "p_critical": float(cols["p_critical"][j]),
        "rank_in_day": int(rank[j]),
        "top_reason": cols["top_reason"][j],
        "truth": {"fraud": int(cols["fraud"][j]), "critical": int(cols["critical"][j])},
    } for j in range(len(idx))]
    n = len(idx)
    return py({"day": day, "date": e.rd.dates[day], "n": n, "capacity": int(math.ceil(rate * n)),
               "rate": rate, "explore": explore, "items": items,
               "truth_note": "Truth labels are shown for the demo only (known after inspection)."})


@app.get("/api/declaration/{decl_id}")
def declaration(decl_id: str, rate: float = C.DEFAULT_RATE, explore: float = 0.0) -> dict:
    _check_rate(rate, explore)
    e = engine()
    if decl_id not in e.pos:
        raise HTTPException(404, "Declaration not found in the test period")
    i = e.pos[decl_id]
    r = e.test.iloc[i]
    lanes = e.lanes(rate, explore)
    lane = str(lanes["lane"][i])
    alert, explored = bool(lanes["alert"][i]), bool(lanes["explored"][i])
    rf, rc = reasons_of(r)
    day = int(e.rd.day[i])
    idx = e.rd.day_rows[day]
    cap = int(math.ceil(rate * len(idx)))
    ai_rank = int((e.rd.s_fraud[idx] > e.rd.s_fraud[i]).sum()) + 1
    rule_rank = int((e.rd.rule[idx] > e.rd.rule[i]).sum()) + 1
    rule_sel = bool(lanes["rule_selected"][i])
    tm_f = e.models["fraud"]
    hs_sum, hs_cnt = tm_f.encoder.stats(pd.DataFrame({"HS6 Code": [int(r["hs6"])]}), "HS6 Code", "hs6")
    hs_rate = float(hs_sum[0] / hs_cnt[0]) if hs_cnt[0] > 0 else None
    past = [x for x in D.read_all() if x.get("declaration_id") == decl_id]
    unit_value = float(r["item_price"]) / max(float(r["net_mass"]), 0.1)
    return py({
        "declaration": {
            "id": decl_id, "date": r["date"], "hs6": str(int(r["hs6"])).zfill(6), "hs_desc": r["hs_desc"],
            "office": int(r["office"]), "office_label": r["office_label"],
            "transport": int(r["transport"]), "transport_label": r["transport_label"],
            "origin": r["origin"], "departure": r["departure"], "importer": r["importer"],
            "declarant": r["declarant"], "seller": None if _missing(r["seller"]) else r["seller"],
            "courier": r["courier"] or None,
            "process_type": r["process_type"], "import_type": int(r["import_type"]),
            "import_use": int(r["import_use"]), "payment_type": int(r["payment_type"]),
            "tax_type": r["tax_type"], "origin_indicator": r["origin_indicator"],
            "tax_rate": float(r["tax_rate"]), "net_mass": float(r["net_mass"]),
            "item_price": float(r["item_price"]), "unit_value": unit_value,
        },
        "ai": {
            "p_fraud": float(r["p_fraud"]), "p_critical": float(r["p_critical"]),
            "fraud_percentile": e.percentile("fraud", float(r["score_fraud"])),
            "critical_percentile": e.percentile("critical", float(r["score_critical"])),
            "lane": lane, "alert": alert, "explored": explored,
            "lane_reason": lane_reason(lane, alert, explored),
            "rank_in_day": ai_rank,
            "reasons_fraud": rf[:4], "reasons_critical": rc[:2],
        },
        "rule": {
            "name": "Product (HS6) history",
            "score": float(r["rule_score"]),
            "hs6_past_declarations": int(hs_cnt[0]),
            "hs6_past_fraud_rate": hs_rate,
            "rank_in_day": rule_rank,
            "selected": rule_sel,
            "decision": "INSPECT" if rule_sel else "RELEASE",
            "explanation": (f"The rule inspects the {cap} declarations of the day whose product has the "
                            f"highest past fraud rate; this one ranks {rule_rank} of {len(idx)}."),
        },
        "day": {"index": day, "date": e.rd.dates[day], "n": int(len(idx)), "capacity": cap, "rate": rate},
        "truth": {"fraud": int(r["fraud"]), "critical": int(r["critical"]),
                  "critical_code": int(r["critical_code"]),
                  "note": "Known after inspection - shown for the demo only."},
        "history": {
            "importer": operator_history("importer", r["importer"]),
            "declarant": operator_history("declarant", r["declarant"]),
            "seller": operator_history("seller", r["seller"]),
            "average_fraud_rate": train_index()["prior_fraud"],
        },
        "network": small_network(r["declarant"], r["seller"], r["importer"]),
        "decisions": past,
    })


@app.post("/api/score")
def score(req: ScoreRequest) -> dict:
    if not re.fullmatch(r"\d{4,6}", req.hs6.strip()):
        raise HTTPException(422, "hs6 must be a 6-digit HS code")
    if req.net_mass < 0 or req.item_price < 0:
        raise HTTPException(422, "mass and price must be positive")
    return py(score_new(req.model_dump(), engine()))


@lru_cache(maxsize=1)
def _presets() -> list[dict]:
    e = engine()
    t = e.test.copy()
    known = t["importer"].isin(train_index()["stats"]["importer"].index) & \
        t["declarant"].isin(train_index()["stats"]["declarant"].index)
    matched = ~t["hs_desc"].str.startswith("HS ")
    base = t[known & matched & t["seller"].notna()]
    picks = [
        ("high_fraud", "High duty-fraud risk", "Real test declaration with one of the highest duty-fraud scores.",
         base.sort_values("score_fraud", ascending=False).iloc[0]),
        ("safety_alert", "Public-safety alert", "Real test declaration flagged by the critical-fraud model.",
         base[base["alert"]].sort_values("score_critical", ascending=False).iloc[0]),
        ("low_risk", "Low risk", "Real test declaration released in the green lane.",
         base[(base["lane"] == "GREEN") & (base["tax_rate"] > 0)].sort_values("score_fraud").iloc[len(base) // 50]),
    ]
    out = []
    for key, label, desc, r in picks:
        out.append({
            "key": key, "label": label, "description": desc,
            "source_declaration_id": r["declaration_id"],
            "declaration": {
                "hs6": str(int(r["hs6"])).zfill(6), "origin": r["origin"], "office": int(r["office"]),
                "importer_id": r["importer"], "declarant_id": r["declarant"], "seller_id": r["seller"],
                "tax_rate": round(float(r["tax_rate"]), 2), "net_mass": round(float(r["net_mass"]), 2),
                "item_price": round(float(r["item_price"]), 2), "transport": int(r["transport"]),
            },
            "hs_desc": r["hs_desc"],
        })
    return py(out)


@app.get("/api/presets")
def presets() -> list:
    return _presets()


@app.get("/api/hs/search")
def hs_search(q: str = Query("", max_length=80)) -> list:
    q = q.strip().lower()
    if len(q) < 2:
        return []
    seen = train_index()["hs6_seen"]
    out = []
    for code, desc in hs_table().items():
        if len(code) != 6:
            continue
        if code.startswith(q) or q in desc.lower():
            n = int(seen.get(int(code), 0))
            out.append({"hs6": code, "description": desc, "past_declarations": n})
    out.sort(key=lambda x: (-x["past_declarations"], x["hs6"]))
    return out[:20]


@app.post("/api/decision")
def decision(req: DecisionRequest) -> dict:
    e = engine()
    ai = {}
    if req.declaration_id in e.pos:
        r = e.test.iloc[e.pos[req.declaration_id]]
        lanes = e.lanes(C.DEFAULT_RATE, 0.0)
        ai = {"lane": str(lanes["lane"][e.pos[req.declaration_id]]),
              "p_fraud": round(float(r["p_fraud"]), 4), "p_critical": round(float(r["p_critical"]), 4)}
    rec = D.append(req.declaration_id, req.decision, req.comment.strip()[:500], req.officer.strip()[:80] or "Officer", ai=ai)
    return {"id": rec["id"], "hash": rec["hash"], "prev_hash": rec["prev_hash"], "ts": rec["ts"]}


@app.get("/api/decisions")
def decisions(limit: int = 200) -> dict:
    entries = D.read_all()
    return {"entries": list(reversed(entries))[: max(1, min(limit, 1000))], "verify": D.verify()}


# ---------------------------------------------------------------------------- SPA
if (C.FRONTEND_DIST / "index.html").exists():
    if (C.FRONTEND_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=C.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "Not found")
        f = (C.FRONTEND_DIST / full_path).resolve()
        if full_path and f.is_file() and C.FRONTEND_DIST.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(C.FRONTEND_DIST / "index.html")
