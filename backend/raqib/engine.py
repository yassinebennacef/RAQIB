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
from .model import TargetModel

REQUIRED = [
    "models/fraud_model.joblib", "models/critical_model.joblib",
    "models/thresholds.json", "models/context.joblib",
    "test_scored.parquet", "metrics.json", "data_card.json",
]


def artifacts_status() -> dict[str, bool]:
    return {name: (C.ARTIFACTS / name).exists() for name in REQUIRED + ["replay_default.json"]}


class Engine:
    def __init__(self) -> None:
        self.models = {t: TargetModel.load(t) for t in C.TARGETS}
        self.thresholds = json.loads((C.MODELS_DIR / "thresholds.json").read_text(encoding="utf-8"))
        self.context = joblib.load(C.MODELS_DIR / "context.joblib")
        self.test = pd.read_parquet(C.ARTIFACTS / "test_scored.parquet")
        self.test["declaration_id"] = self.test["declaration_id"].astype(str)
        self.pos = {did: i for i, did in enumerate(self.test["declaration_id"])}
        self.rd = R.prepare(self.test, alert_thr=self.thresholds["alert_threshold"])
        self.metrics = json.loads((C.ARTIFACTS / "metrics.json").read_text(encoding="utf-8"))
        self.data_card = json.loads((C.ARTIFACTS / "data_card.json").read_text(encoding="utf-8"))
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
