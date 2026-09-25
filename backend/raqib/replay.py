"""Day-by-day replay of the TEST period under a fixed daily inspection capacity.

For every day: capacity = ceil(rate x declarations that day), IDENTICAL for every policy.
- ai:          public-safety alerts first (p_critical >= 99th pct of TEST p_critical),
               then the highest p_fraud; no exploration.
- ai_explore:  same, but a share `explore` of the capacity is drawn at random from the
               declarations the model did not pick (stochastic rounding, seeded).
- rule:        top of the day by product (HS6) fraud history.
- random:      random sample.
AI lanes: RED = selected, YELLOW = next 10% of the day by p_fraud, GREEN = the rest.
Ranking uses the raw model scores (same order as the calibrated probabilities, no ties).
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from . import config as C

POLICIES = ["ai", "ai_explore", "rule", "random"]
POLICY_LABELS = {
    "ai": "RAQIB AI",
    "ai_explore": "RAQIB AI + exploration",
    "rule": "Current rule (product history)",
    "random": "Random",
}


@dataclass
class ReplayData:
    day: np.ndarray
    dates: list[str]
    day_rows: list[np.ndarray]
    fraud: np.ndarray
    critical: np.ndarray
    s_fraud: np.ndarray
    s_crit: np.ndarray
    rule: np.ndarray
    hs6: np.ndarray
    tiebreak: np.ndarray
    alert_thr: float


def prepare(df: pd.DataFrame, alert_thr: float | None = None) -> ReplayData:
    """df = test_scored (any order); rows are addressed by position."""
    dates = pd.to_datetime(df["date"])
    uniq = np.sort(dates.unique())
    day = np.searchsorted(uniq, dates.to_numpy())
    s_crit = df["score_critical"].to_numpy(float)
    thr = float(np.quantile(s_crit, C.ALERT_QUANTILE)) if alert_thr is None else float(alert_thr)
    return ReplayData(
        day=day,
        dates=[str(pd.Timestamp(d).date()) for d in uniq],
        day_rows=[np.where(day == i)[0] for i in range(len(uniq))],
        fraud=df["fraud"].to_numpy(int),
        critical=df["critical"].to_numpy(int),
        s_fraud=df["score_fraud"].to_numpy(float),
        s_crit=s_crit,
        rule=df["rule_score"].to_numpy(float),
        hs6=df["hs6"].to_numpy(int),
        tiebreak=np.random.default_rng(0).permutation(len(df)).astype(float),
        alert_thr=thr,
    )


def capacity(n: int, rate: float) -> int:
    return int(np.ceil(rate * n))


def _ranked(idx: np.ndarray, score: np.ndarray, tiebreak: np.ndarray) -> np.ndarray:
    return idx[np.lexsort((tiebreak[idx], -score[idx]))]


def select_day(policy: str, idx: np.ndarray, cap: int, d: ReplayData, rng, explore: float):
    """Return (selected rows, explored rows) for one day."""
    empty = np.array([], dtype=int)
    cap = min(cap, len(idx))
    if cap <= 0:
        return empty, empty
    if policy == "random":
        return rng.choice(idx, size=cap, replace=False), empty
    if policy == "rule":
        return _ranked(idx, d.rule, d.tiebreak)[:cap], empty
    # AI policies
    alerts = idx[d.s_crit[idx] >= d.alert_thr]
    alerts = _ranked(alerts, d.s_crit, d.tiebreak)[:cap]
    rest = np.setdiff1d(idx, alerts, assume_unique=True)
    remaining = cap - len(alerts)
    n_exp = 0
    if policy == "ai_explore" and explore > 0:
        u = rng.random()
        n_exp = min(remaining, int(np.floor(explore * cap + u)))
    ranked = _ranked(rest, d.s_fraud, d.tiebreak)
    top = ranked[: remaining - n_exp]
    pool = ranked[remaining - n_exp:]
    explored = rng.choice(pool, size=min(n_exp, len(pool)), replace=False) if n_exp > 0 else empty
    return np.concatenate([alerts, top, explored]).astype(int), np.asarray(explored, dtype=int)


def run_policy(d: ReplayData, policy: str, rate: float, explore: float, seed: int = C.REPLAY_SEED):
    rng = np.random.default_rng(seed)
    n_rows = len(d.day)
    selected = np.zeros(n_rows, bool)
    explored_mask = np.zeros(n_rows, bool)
    series = {k: [] for k in ("frauds", "threats", "explored", "explored_frauds", "alerts")}
    for idx in d.day_rows:
        cap = capacity(len(idx), rate)
        sel, exp = select_day(policy, idx, cap, d, rng, explore)
        selected[sel] = True
        explored_mask[exp] = True
        series["frauds"].append(int(d.fraud[sel].sum()))
        series["threats"].append(int(d.critical[sel].sum()))
        series["explored"].append(int(len(exp)))
        series["explored_frauds"].append(int(d.fraud[exp].sum()))
        series["alerts"].append(int((d.s_crit[idx] >= d.alert_thr).sum()) if policy.startswith("ai") else 0)
    return selected, explored_mask, series


def ai_lanes(d: ReplayData, selected: np.ndarray, rate: float) -> np.ndarray:
    lanes = np.full(len(d.day), "GREEN", dtype=object)
    lanes[selected] = "RED"
    for idx in d.day_rows:
        rest = idx[~selected[idx]]
        n_yellow = int(np.ceil(C.YELLOW_SHARE * len(idx)))
        yellow = _ranked(rest, d.s_fraud, d.tiebreak)[:n_yellow]
        lanes[yellow] = "YELLOW"
    return lanes


def replay(d: ReplayData, rate: float = C.DEFAULT_RATE, explore: float = C.DEFAULT_EXPLORE,
           seed: int = C.REPLAY_SEED) -> dict:
    n_per_day = [int(len(idx)) for idx in d.day_rows]
    caps = [capacity(n, rate) for n in n_per_day]
    out = {
        "rate": rate,
        "explore": explore,
        "seed": seed,
        "n_days": len(d.dates),
        "dates": d.dates,
        "n": n_per_day,
        "capacity": caps,
        "day_frauds": [int(d.fraud[idx].sum()) for idx in d.day_rows],
        "day_threats": [int(d.critical[idx].sum()) for idx in d.day_rows],
        "alert_threshold": d.alert_thr,
        "totals": {
            "declarations": int(len(d.day)),
            "frauds": int(d.fraud.sum()),
            "threats": int(d.critical.sum()),
            "inspections": int(sum(caps)),
        },
        "policies": {},
    }
    for policy in POLICIES:
        selected, explored, s = run_policy(d, policy, rate, explore if policy == "ai_explore" else 0.0, seed)
        cum_f = np.cumsum(s["frauds"]).tolist()
        cum_t = np.cumsum(s["threats"]).tolist()
        cum_i = np.cumsum([int(selected[idx].sum()) for idx in d.day_rows]).tolist()
        seen: set[int] = set()
        distinct = []
        for idx in d.day_rows:
            seen.update(d.hs6[idx[selected[idx]]].tolist())
            distinct.append(len(seen))
        p = {
            "label": POLICY_LABELS[policy],
            "frauds": s["frauds"],
            "threats": s["threats"],
            "cum_frauds": cum_f,
            "cum_threats": cum_t,
            "cum_inspected": cum_i,
            "distinct_hs6": distinct,
            "explored": s["explored"],
            "explored_frauds": s["explored_frauds"],
        }
        summary = {
            "inspections": int(selected.sum()),
            "frauds": int(cum_f[-1]) if cum_f else 0,
            "threats": int(cum_t[-1]) if cum_t else 0,
            "hit_rate": float(cum_f[-1] / max(selected.sum(), 1)) if cum_f else 0.0,
            "fraud_recall": float(cum_f[-1] / max(d.fraud.sum(), 1)) if cum_f else 0.0,
            "threat_recall": float(cum_t[-1] / max(d.critical.sum(), 1)) if cum_t else 0.0,
            "distinct_hs6": int(distinct[-1]) if distinct else 0,
            "explored": int(sum(s["explored"])),
            "explored_frauds": int(sum(s["explored_frauds"])),
        }
        if policy.startswith("ai"):
            lanes = ai_lanes(d, selected, rate)
            p["red"] = [int((lanes[idx] == "RED").sum()) for idx in d.day_rows]
            p["yellow"] = [int((lanes[idx] == "YELLOW").sum()) for idx in d.day_rows]
            p["green"] = [int((lanes[idx] == "GREEN").sum()) for idx in d.day_rows]
            p["alerts"] = s["alerts"]
            summary["green_share"] = float((lanes == "GREEN").mean())
            summary["yellow_share"] = float((lanes == "YELLOW").mean())
        p["summary"] = summary
        out["policies"][policy] = p
    return out


def lanes_for(d: ReplayData, rate: float, explore: float, seed: int = C.REPLAY_SEED) -> dict:
    """Per-row AI lanes (with the given exploration) and the rule's selection."""
    policy = "ai_explore" if explore > 0 else "ai"
    selected, explored, _ = run_policy(d, policy, rate, explore, seed)
    rule_sel, _, _ = run_policy(d, "rule", rate, 0.0, seed)
    return {
        "lane": ai_lanes(d, selected, rate),
        "explored": explored,
        "rule_selected": rule_sel,
        "alert": d.s_crit >= d.alert_thr,
    }


def summary_table(r: dict) -> list[str]:
    lines = [f"\nDaily replay: capacity {r['rate']:.0%} of each day ({r['totals']['inspections']} inspections over "
             f"{r['n_days']} days), exploration {r['explore']:.0%}; TEST has {r['totals']['frauds']} frauds, "
             f"{r['totals']['threats']} threats"]
    lines.append(f"  {'policy':34s} {'insp.':>6s} {'frauds':>7s} {'threats':>8s} {'hit rate':>9s} {'HS6 seen':>9s}")
    for p, v in r["policies"].items():
        s = v["summary"]
        lines.append(f"  {v['label']:34s} {s['inspections']:6d} {s['frauds']:7d} {s['threats']:8d} "
                     f"{s['hit_rate']:9.3f} {s['distinct_hs6']:9d}")
    return lines

