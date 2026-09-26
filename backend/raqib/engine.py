"""Loads the built artifacts once (models, encodings, TEST scores) for the API and scoring."""
from __future__ import annotations

import json
import threading
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from . import config as C
from . import replay as R

TRAIN_INDEX = C.ARTIFACTS / "train_index.joblib"


def build_train_index(train: pd.DataFrame) -> dict:
    """Past (TRAIN) relations used for operator history and the small network."""
    pairs = {}
    for role, col in (("declarant", "Declarant ID"), ("seller", "Seller ID")):
        g = train.groupby([col, "Importer ID"]).size().rename("n").reset_index()
        pairs[role] = {k: v.sort_values("n", ascending=False) for k, v in g.groupby(col)}
    stats = {}
    for role, col in (("importer", "Importer ID"), ("declarant", "Declarant ID"), ("seller", "Seller ID")):
        stats[role] = train.groupby(col).agg(n=("fraud", "size"), frauds=("fraud", "sum"),
                                             criticals=("critical", "sum"))
    return {"pairs": pairs, "stats": stats, "hs6_seen": train["HS6 Code"].value_counts(),
            "prior_fraud": float(train["fraud"].mean()), "prior_critical": float(train["critical"].mean())}


@lru_cache(maxsize=1)
def load_train_index() -> dict:
    if TRAIN_INDEX.exists():
        return joblib.load(TRAIN_INDEX)
    from .data import load_train
    idx = build_train_index(load_train())
    joblib.dump(idx, TRAIN_INDEX)
    return idx


REQUIRED = [
    "models/fraud_model.joblib", "models/critical_model.joblib",
    "models/thresholds.json", "models/context.joblib",
    "test_scored.parquet", "metrics.json", "data_card.json", "train_index.joblib", "hs_names.json",
    "models/fraud_ebm.joblib", "models/critical_ebm.joblib", "models/primary.json",
    "efficiency.json", "experiments.json", "xai_global.json",
]


def artifacts_status() -> dict[str, bool]:
    return {name: (C.ARTIFACTS / name).exists() for name in REQUIRED + ["replay_default.json"]}


def _optional_json(name: str):
    path = C.ARTIFACTS / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


class Engine:
    def __init__(self) -> None:
        from .twin import load_twins
        self.twins = load_twins()
        self.models = {t: tw.lgbm for t, tw in self.twins.items()}
        self.thresholds = json.loads((C.MODELS_DIR / "thresholds.json").read_text(encoding="utf-8"))
        self.context = joblib.load(C.MODELS_DIR / "context.joblib")
        self.test = pd.read_parquet(C.ARTIFACTS / "test_scored.parquet")
        self.test["declaration_id"] = self.test["declaration_id"].astype(str)
        self.pos = {did: i for i, did in enumerate(self.test["declaration_id"])}
        self.rd = R.prepare(self.test, alert_thr=self.thresholds["alert_threshold"])
        self.metrics = json.loads((C.ARTIFACTS / "metrics.json").read_text(encoding="utf-8"))
        self.data_card = json.loads((C.ARTIFACTS / "data_card.json").read_text(encoding="utf-8"))
        self.efficiency = _optional_json("efficiency.json")
        self.experiments = _optional_json("experiments.json")
        self.xai_global = _optional_json("xai_global.json")
        self.model_card = _optional_json("model_card.json")
        self._lock = threading.Lock()
        self._replay_cache: dict[tuple[float, float], dict] = {}
        self._lanes_cache: dict[tuple[float, float], dict] = {}

    # ---- replay (cached by parameters) ---------------------------------------
    def replay(self, rate: float, explore: float) -> dict:
        key = (round(rate, 4), round(explore, 4))
        with self._lock:
            if key not in self._replay_cache:
                self._replay_cache[key] = R.replay(self.rd, rate=key[0], explore=key[1])
            return self._replay_cache[key]

    def lanes(self, rate: float, explore: float) -> dict:
        key = (round(rate, 4), round(explore, 4))
        with self._lock:
            if key not in self._lanes_cache:
                self._lanes_cache[key] = R.lanes_for(self.rd, rate=key[0], explore=key[1])
            return self._lanes_cache[key]

    # ---- helpers ---------------------------------------------------------------
    def percentile(self, target: str, raw: float) -> float:
        arr = self.context[f"test_sorted_{target}"]
        return float(100.0 * np.searchsorted(arr, raw, side="right") / len(arr))


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return Engine()


def reset_engine() -> None:
    get_engine.cache_clear()
