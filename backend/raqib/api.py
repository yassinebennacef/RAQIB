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
from .data import hs_description, hs_table
from .engine import Engine, artifacts_status, get_engine, load_train_index
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
        try:
            _pregenerate_briefs()
            from .llm import client as _llm
            st = _llm.status()
            print(f"[raqib] local LLM: {st['mode']} ({st['model'] or 'template mode'})", flush=True)
        except Exception as exc:  # noqa: BLE001 - the LLM is optional
            print(f"[raqib] local LLM off ({exc})", flush=True)
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


def train_index() -> dict:
    """Past (TRAIN) relations: operator history, network, HS6 frequencies (saved by the build)."""
    return load_train_index()


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
    return {"nodes": list(nodes.values()), "links": links, "context_only": True,
            "note": "Context only: past relations (TRAIN period). Fraud rate = share of an importer's past "
                    "declarations found fraudulent. Network features were tested and rejected as model inputs."}


def reasons_of(row: pd.Series) -> tuple[list, list]:
    return json.loads(row["reasons_fraud"]), json.loads(row["reasons_critical"])


def lane_reason(lane: str, alert: bool, explored: bool, uncertain_only: bool = False) -> str:
    if lane == "YELLOW" and uncertain_only:
        return "The glass-box and black-box models disagree strongly: human review (never released green)."
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
                                         "p_critical", "top_reason", "fraud", "critical",
                                         "uncertain", "disagreement")}
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
        "uncertain": bool(cols["uncertain"][j]),
        "disagreement": float(cols["disagreement"][j]),
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
    uncertain = bool(r["uncertain"])
    by_risk_yellow = ai_rank <= cap + int(math.ceil(C.YELLOW_SHARE * len(idx)))
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
            "lane_reason": lane_reason(lane, alert, explored, uncertain and not by_risk_yellow),
            "rank_in_day": ai_rank,
            "reasons_fraud": rf[:4], "reasons_critical": rc[:2],
            "uncertain": uncertain, "disagreement": float(r["disagreement"]),
            "models": {"primary": {t: tw.primary for t, tw in e.twins.items()},
                       "lightgbm": {"p_fraud": float(r["p_fraud_lgbm"]), "p_critical": float(r["p_critical_lgbm"])},
                       "ebm": {"p_fraud": float(r["p_fraud_ebm"]), "p_critical": float(r["p_critical_ebm"])}},
        },
        "waterfall": json.loads(r["waterfall_fraud"]),
        "waterfall_critical": json.loads(r["waterfall_critical"]),
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


# ---------------------------------------------------------------------------- v2 endpoints
class WhatIfRequest(BaseModel):
    declaration_id: str | None = None
    declaration: ScoreRequest | None = None
    changes: dict[str, Any] = Field(default_factory=dict)


def _csv(v: str | None) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


@app.get("/api/worklist")
def worklist(day: int | None = None, lane: str | None = None, origin: str | None = None, hs2: str | None = None,
             office: str | None = None, uncertain: bool | None = None, min_p: float | None = None,
             q: str | None = None, sort: str = "p_fraud", order: str = "desc", page: int = 1,
             page_size: int = Query(50, ge=1, le=500), rate: float = C.DEFAULT_RATE, explore: float = 0.0,
             hs_prefix: str | None = None, importer: str | None = None, date_from: str | None = None,
             date_to: str | None = None, alert: bool | None = None) -> dict:
    _check_rate(rate, explore)
    e = engine()
    t = e.test
    lanes = e.lanes(rate, explore)
    df = pd.DataFrame({
        "day": e.rd.day, "lane": lanes["lane"].astype(str), "alert": lanes["alert"],
        "rule_selected": lanes["rule_selected"], "hs2": (t["hs6"] // 10000).astype(int).astype(str).str.zfill(2),
    })
    mask = np.ones(len(t), bool)
    if day is not None:
        mask &= df["day"].to_numpy() == day
    base_mask = mask.copy()  # facets reflect the day filter only
    if lane:
        mask &= df["lane"].isin([x.upper() for x in _csv(lane)]).to_numpy()
    if origin:
        mask &= t["origin"].isin([x.upper() for x in _csv(origin)]).to_numpy()
    if hs2:
        mask &= df["hs2"].isin([x.zfill(2) for x in _csv(hs2)]).to_numpy()
    if office:
        mask &= t["office"].astype(str).isin(_csv(office)).to_numpy()
    if uncertain is not None:
        mask &= t["uncertain"].to_numpy(bool) == uncertain
    if min_p is not None:
        mask &= t["p_fraud"].to_numpy(float) >= min_p
    if hs_prefix:
        hs6s = t["hs6"].astype(int).astype(str).str.zfill(6)
        pref = tuple(x for x in _csv(hs_prefix) if x.isdigit())
        if pref:
            mask &= hs6s.str.startswith(pref).to_numpy()
    if importer:
        mask &= (t["importer"].fillna("").str.upper() == importer.strip().upper()).to_numpy()
    if date_from:
        mask &= (t["date"] >= date_from[:10]).to_numpy()
    if date_to:
        mask &= (t["date"] <= date_to[:10]).to_numpy()
    if alert is not None:
        mask &= df["alert"].to_numpy(bool) == alert
    if q and q.strip():
        qq = q.strip().lower()
        hay = (t["declaration_id"] + " " + t["hs6"].astype(str).str.zfill(6) + " " + t["hs_desc"].str.lower() + " "
               + t["importer"].fillna("").str.lower() + " " + t["declarant"].fillna("").str.lower() + " "
               + t["seller"].fillna("").str.lower())
        mask &= hay.str.contains(qq, regex=False).to_numpy()
    keys = {"p_fraud": t["p_fraud"], "p_critical": t["p_critical"], "date": t["date"],
            "disagreement": t["disagreement"], "item_price": t["item_price"]}
    if sort not in keys:
        raise HTTPException(422, f"sort must be one of {', '.join(keys)}")
    sel = np.where(mask)[0]
    sel = sel[np.argsort(keys[sort].to_numpy()[sel], kind="mergesort")]
    if order == "desc":
        sel = sel[::-1]
    total = int(len(sel))
    page = max(page, 1)
    chunk = sel[(page - 1) * page_size: page * page_size]
    items = []
    for i in chunk:
        r = t.iloc[i]
        items.append({
            "id": r["declaration_id"], "date": r["date"], "day": int(e.rd.day[i]),
            "hs6": str(int(r["hs6"])).zfill(6), "hs_desc": r["hs_desc"], "hs2": df["hs2"].iat[i],
            "origin": r["origin"], "office": int(r["office"]), "office_label": r["office_label"],
            "transport_label": r["transport_label"], "item_price": float(r["item_price"]),
            "lane": df["lane"].iat[i], "alert": bool(df["alert"].iat[i]), "uncertain": bool(r["uncertain"]),
            "disagreement": float(r["disagreement"]), "p_fraud": float(r["p_fraud"]),
            "p_critical": float(r["p_critical"]), "top_reason": r["top_reason"],
            "rule_decision": "INSPECT" if bool(df["rule_selected"].iat[i]) else "RELEASE",
            "truth": {"fraud": int(r["fraud"]), "critical": int(r["critical"])},
        })
    b = base_mask

    def top_values(series: pd.Series, n: int = 25, label=None) -> list[dict]:
        vc = series[b].value_counts().head(n)
        return [{"value": str(k), "n": int(v), **({"label": label(k)} if label else {})} for k, v in vc.items()]

    facets = {
        "lane": {k: int(v) for k, v in df.loc[b, "lane"].value_counts().items()},
        "uncertain": {str(k).lower(): int(v) for k, v in t.loc[b, "uncertain"].value_counts().items()},
        "origin": top_values(t["origin"]),
        "office": top_values(t["office"].astype(str), label=lambda k: C.office_label(k)),
        "hs2": top_values(df["hs2"], label=lambda k: hs_table().get(str(k).zfill(2), f"HS {k}")),
    }
    return py({"total": total, "page": page, "page_size": page_size, "facets": facets, "items": items})


@app.post("/api/whatif")
def whatif(req: WhatIfRequest) -> dict:
    from .score import frame_from_test_row, to_frame, whatif as run_whatif
    e = engine()
    if req.declaration_id:
        if req.declaration_id not in e.pos:
            raise HTTPException(404, "Declaration not found in the test period")
        df = frame_from_test_row(e.test.iloc[e.pos[req.declaration_id]])
    elif req.declaration is not None:
        df = to_frame(req.declaration.model_dump())
    else:
        raise HTTPException(422, "give declaration_id or declaration")
    try:
        return py(run_whatif(e, df, req.changes or {}))
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, f"invalid change: {exc}") from exc


@app.get("/api/efficiency")
def efficiency(minutes_per_inspection: float = Query(60.0, gt=0, le=600)) -> dict:
    from .efficiency import hours
    e = engine()
    if e.efficiency is None:
        raise HTTPException(503, "efficiency.json missing - run python -m raqib.build")
    out = dict(e.efficiency)
    out["officer_hours"] = hours(out["matching"].get("fewer_inspections", 0), len(e.rd.dates), minutes_per_inspection)
    return py(out)


@app.get("/api/experiments")
def experiments() -> dict:
    e = engine()
    if e.experiments is None:
        raise HTTPException(503, "experiments.json missing - run python -m raqib.build")
    return e.experiments


@app.get("/api/xai-global")
def xai_global() -> dict:
    e = engine()
    if e.xai_global is None:
        raise HTTPException(503, "xai_global.json missing - run python -m raqib.build")
    return e.xai_global


@app.get("/api/model-card")
def model_card() -> dict:
    e = engine()
    if e.model_card is None:
        raise HTTPException(503, "model_card.json missing - run python -m raqib.report")
    return e.model_card


def brief_facts(e: Engine, decl_id: str) -> dict:
    from .explain import GROUPS
    from .score import frame_from_test_row
    i = e.pos[decl_id]
    r = e.test.iloc[i]
    lanes = e.lanes(C.DEFAULT_RATE, 0.0)
    rf = json.loads(r["reasons_fraud"])
    top = dict(rf[0]) if rf else None
    if top:
        spec = {g: (col, name) for g, _, _, col, name in GROUPS if col}
        if top["group"] in spec:
            col, name = spec[top["group"]]
            frame = frame_from_test_row(r)
            s_, c_ = e.models["fraud"].encoder.stats(frame, col, name)
            v = frame[col].iat[0]
            widths = {"HS6 Code": 6, "hs4": 4, "hs2": 2}
            if col in widths:
                code = str(int(v)).zfill(widths[col])
            elif col == "Office ID":
                code = C.office_label(v)
            else:
                code = "" if _missing(v) else str(v)
            top.update({"count": int(c_[0]), "rate": float(s_[0] / c_[0]) if c_[0] > 0 else None, "code": code})
        elif top["group"] == "tax":
            top["tax"] = float(r["tax_rate"])
    return {"id": decl_id, "lane": str(lanes["lane"][i]), "p_fraud": float(r["p_fraud"]),
            "p_critical": float(r["p_critical"]), "fraud_percentile": e.percentile("fraud", float(r["score_fraud"])),
            "alert": bool(lanes["alert"][i]), "uncertain": bool(r["uncertain"]),
            "rule_decision": "INSPECT" if bool(lanes["rule_selected"][i]) else "RELEASE",
            "avg_fraud": float(e.models["fraud"].prior), "top": top}


@app.post("/api/brief/{decl_id}")
def brief(decl_id: str, lang: Literal["fr", "en", "ar"] = "fr") -> dict:
    from .brief import template_brief
    e = engine()
    if decl_id not in e.pos:
        raise HTTPException(404, "Declaration not found in the test period")
    facts = brief_facts(e, decl_id)
    return py({"id": decl_id, "lang": lang, "text": template_brief(facts, lang), "source": "template",
               "model": None, "cached": False, "facts": facts})


# ---------------------------------------------------------------------------- local LLM (optional)
class BriefRequest(BaseModel):
    id: str
    lang: Literal["fr", "ar", "en"] = "fr"
    refresh: bool = False


class NLQRequest(BaseModel):
    q: str = Field(..., max_length=2000)  # long questions are truncated by the parser, never rejected


class WorklistQuery(BaseModel):
    filter: dict[str, Any] = Field(default_factory=dict)
    page: int = 1
    page_size: int | None = None


def _llm_brief_inputs(decl_id: str) -> tuple[dict, str]:
    from .brief import template_brief
    from .llm.brief import facts_from_detail
    e = engine()
    detail = declaration(decl_id)
    lang_facts = brief_facts(e, decl_id)
    return facts_from_detail(detail), lang_facts


@lru_cache(maxsize=1)
def _nlq_vocab():
    from .llm.nlq import Vocab
    e = engine()
    t = e.test
    offices = {str(int(o)): C.office_label(o) for o in sorted(t["office"].unique())}
    return Vocab(origins=set(t["origin"].dropna().astype(str)), offices=offices,
                 hs6=set(t["hs6"].astype(int).astype(str).str.zfill(6)),
                 importers=set(t["importer"].dropna().astype(str).str.upper()),
                 date_min=e.rd.dates[0], date_max=e.rd.dates[-1])


@app.post("/api/brief")
def brief_llm(req: BriefRequest) -> dict:
    from .brief import template_brief
    from .llm import brief as LB
    e = engine()
    if req.id not in e.pos:
        raise HTTPException(404, "Declaration not found in the test period")
    facts, tfacts = _llm_brief_inputs(req.id)
    return py(LB.brief(req.id, req.lang, facts, template_brief(tfacts, req.lang), refresh=req.refresh))


@app.post("/api/nlq")
def nlq(req: NLQRequest) -> dict:
    from .llm.nlq import parse
    return py(parse(req.q, _nlq_vocab()))


def filter_to_params(f: dict) -> dict:
    sort = {"fraud_desc": ("p_fraud", "desc"), "critical_desc": ("p_critical", "desc"),
            "date_desc": ("date", "desc")}.get(f.get("sort") or "fraud_desc", ("p_fraud", "desc"))
    return {
        "lane": ",".join(f.get("lane") or []) or None, "origin": ",".join(f.get("origin") or []) or None,
        "office": ",".join(f.get("office") or []) or None, "hs_prefix": ",".join(f.get("hs_prefix") or []) or None,
        "uncertain": True if f.get("uncertain_only") else None, "alert": True if f.get("safety_only") else None,
        "min_p": f.get("min_fraud"), "importer": f.get("importer"), "date_from": f.get("date_from"),
        "date_to": f.get("date_to"), "sort": sort[0], "order": sort[1],
    }


@app.post("/api/worklist/query")
def worklist_query(req: WorklistQuery) -> dict:
    """Apply a validated "Ask RAQIB" filter to the worklist (same response shape as GET /api/worklist)."""
    from .llm.nlq import validate
    f, _ = validate(req.filter or {}, _nlq_vocab())
    fd = f.model_dump()
    return worklist(**filter_to_params(fd), page=max(req.page, 1), page_size=req.page_size or fd["limit"])


@app.get("/api/llm/status")
def llm_status() -> dict:
    from .llm import client
    return client.refresh_status() | {"warm": client.status()["warm"]}


@app.get("/api/llm/eval")
def llm_eval() -> dict:
    path = C.ARTIFACTS / "llm_eval.json"
    if not path.exists():
        return {"skipped": True, "reason": "run python scripts/eval_llm.py"}
    return json.loads(path.read_text(encoding="utf-8"))


class AssistantRequest(BaseModel):
    messages: list[dict[str, Any]] = Field(default_factory=list)
    lang: Literal["fr", "ar", "en"] = "fr"
    page: str = "/"
    declaration_id: str | None = None


@app.post("/api/assistant")
def assistant(req: AssistantRequest) -> dict:
    """Grounded helper chat: explains from the knowledge base and the computed facts; never scores or decides."""
    from .llm.assistant import answer
    from .llm.nlq import parse
    e = engine()
    did = req.declaration_id
    if not did:
        m = re.match(r"/declaration/([\w-]+)", req.page or "")
        did = m.group(1) if m else None
    facts = _llm_brief_inputs(did)[0] if did and did in e.pos else None
    msgs = [{"role": str(x.get("role", "user")), "content": str(x.get("content", ""))[:800]} for x in req.messages[-6:]]
    out = answer(msgs, req.lang, req.page or "/", facts, nlq_parse=lambda q: parse(q, _nlq_vocab()))
    return py({**out, "declaration_id": did if facts else None})


def _pregenerate_briefs() -> None:
    from .llm import brief as LB
    from .llm import client
    client.refresh_status()
    if not client.available():
        return
    e = engine()
    top = worklist(lane="RED", uncertain=False, page_size=20)["items"]
    ids = [i for i in ("54794554", "80928101") if i in e.pos] + [it["id"] for it in top]
    jobs = [(i, "fr") for i in dict.fromkeys(ids)] + [(i, lang) for i in ids[:2] for lang in ("ar", "en")]

    def build(decl_id: str):
        from .brief import template_brief
        facts, tfacts = _llm_brief_inputs(decl_id)
        return facts, template_brief(tfacts, "fr")

    LB.pregenerate(jobs, build)
    from .llm import assistant as AS
    # starters of the assistant, after the briefs (Ollama queues the requests)
    AS.pregenerate(lambda d: _llm_brief_inputs(d)[0], [i for i in ("54794554", "80928101") if i in e.pos])


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
        # never cache the page itself, so the browser always loads the latest build (assets are content-hashed)
        return FileResponse(C.FRONTEND_DIST / "index.html", headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
