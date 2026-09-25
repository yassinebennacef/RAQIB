"""'Current practice' baselines on TEST, with the same smoothing as the model.

- random (seed 0)
- rule_importer_history: the importer's past rate of the target
- rule_hs6_history: the product's (HS6) past rate of the target (the strongest rule)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def history_rule(train: pd.DataFrame, test: pd.DataFrame, target: str, col: str) -> np.ndarray:
    a = C.TARGETS[target]
    y = train[target].astype(float)
    prior = float(y.mean())
    g = y.groupby(train[col]).agg(["sum", "count"])
    s = test[col].map(g["sum"]).fillna(0.0).to_numpy(dtype=float)
    c = test[col].map(g["count"]).fillna(0.0).to_numpy(dtype=float)
    return (s + a * prior) / (c + a)


def random_scores(n: int, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).random(n)


def baseline_scores(train: pd.DataFrame, test: pd.DataFrame, target: str) -> dict[str, np.ndarray]:
    return {
        "rule_hs6_history": history_rule(train, test, target, "HS6 Code"),
        "rule_importer_history": history_rule(train, test, target, "Importer ID"),
        "random": random_scores(len(test), seed=0),
    }
