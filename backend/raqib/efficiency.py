"""Impact: the same result with fewer inspections (daily replay, same capacity rules as replay.py).

- curve: frauds and threats caught by AI / rule / random for daily capacities 1% .. 20%
- matching: the smallest AI capacity (0.1% steps) whose frauds reach the rule's frauds at 5%
- pooled: the same comparison on one pooled ranking of the whole test period (top-k)
- officer hours freed, from an explicit assumption (minutes per inspection)
"""
from __future__ import annotations

import numpy as np

from . import config as C
from . import replay as R
from .evaluate import order_desc, top_k

RATES = [round(0.01 * k, 2) for k in range(1, 21)]
FINE = [round(0.001 * k, 3) for k in range(5, 201)]  # 0.5% .. 20% by 0.1%
DEFAULT_MINUTES = 60.0


def _run(d: R.ReplayData, policy: str, rate: float) -> dict:
    selected, _, s = R.run_policy(d, policy, rate, 0.0)
    return {"frauds": int(sum(s["frauds"])), "threats": int(sum(s["threats"])), "inspections": int(selected.sum())}


def _smallest_ai_rate(d: R.ReplayData, key: str, target_value: int):
    for r in FINE:
        a = _run(d, "ai", r)
        if a[key] >= target_value:
            return r, a
    return None, None


def hours(fewer_inspections: int, n_days: int, minutes: float) -> dict:
    h = fewer_inspections * minutes / 60.0
    return {"minutes_per_inspection": minutes, "assumption": True,
            "hours_freed_test_period": round(h, 1), "test_days": n_days,
            "hours_freed_per_year": round(h * 365.0 / max(n_days, 1), 1),
            "note": "Assumption: average officer time per physical inspection; edit it to your own figure."}


def compute(d: R.ReplayData, ref_rate: float = C.DEFAULT_RATE, minutes: float = DEFAULT_MINUTES) -> dict:
    curve = []
    for r in RATES:
        a, ru, rn = _run(d, "ai", r), _run(d, "rule", r), _run(d, "random", r)
        curve.append({"rate": r, "inspections": a["inspections"],
                      "ai": {k: a[k] for k in ("frauds", "threats")},
                      "rule": {k: ru[k] for k in ("frauds", "threats")},
                      "random": {k: rn[k] for k in ("frauds", "threats")}})

    ref = _run(d, "rule", ref_rate)
    r_match, a_match = _smallest_ai_rate(d, "frauds", ref["frauds"])
    matching = {"reference": {"policy": "rule", "rate": ref_rate, **ref}}
    if r_match is not None:
        fewer = ref["inspections"] - a_match["inspections"]
        matching.update({"ai_rate": r_match, "ai_inspections": a_match["inspections"], "ai_frauds": a_match["frauds"],
                         "ai_threats": a_match["threats"], "fewer_inspections": fewer,
                         "fewer_pct": fewer / max(ref["inspections"], 1)})

    rt, at = _smallest_ai_rate(d, "threats", ref["threats"])
    threats = {"rule_at_ref": ref["threats"], "ai_rate_matching_threats": rt,
               "ai_inspections": at["inspections"] if at else None}

    # pooled ranking over the whole test period
    n = len(d.fraud)
    k_rule = top_k(n, ref_rate)
    rule_frauds = int(d.fraud[order_desc(d.rule, d.tiebreak)[:k_rule]].sum())
    cum_ai = np.cumsum(d.fraud[order_desc(d.s_fraud, d.tiebreak)])
    k_ai = int(np.searchsorted(cum_ai, rule_frauds) + 1)
    pooled = {"k_rule": k_rule, "rule_frauds": rule_frauds, "k_ai_needed": k_ai,
              "fewer_inspections": k_rule - k_ai, "fewer_pct": (k_rule - k_ai) / k_rule}

    n_days = len(d.dates)
    return {"curve": curve, "matching": matching, "pooled": pooled, "threats": threats,
            "officer_hours": hours(matching.get("fewer_inspections", 0), n_days, minutes),
            "policy_note": "Daily replay without exploration; public-safety alerts take AI slots first."}
