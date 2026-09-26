"""LightGBM (black box) + EBM (glass box) twins per target.

The primary model of a target drives the probabilities shown, the lanes and the replay; the other
one is kept as a twin (and their disagreement is used as an uncertainty signal).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd

from . import config as C
from .explain import ebm_group_contributions, lgbm_group_contributions
from .model import TargetModel

PRIMARY_FILE = C.MODELS_DIR / "primary.json"
MARGIN = 0.015
OPERATING_METRIC = {"fraud": "precision_at_5", "critical": "recall_at_5"}
PRIMARY_RULE = (
    "EBM (glass box) is primary for a target when its operating metric (fraud: precision @5%, "
    "critical: recall @5%) is within 1.5 points of LightGBM or better; otherwise LightGBM stays "
    "primary and EBM is the transparent twin."
)
MODEL_LABELS = {"ebm": "EBM (glass box)", "lightgbm": "LightGBM (gradient boosting)"}


@dataclass
class Twin:
    target: str
    lgbm: TargetModel
    ebm: object | None
    primary: str

    @property
    def encoder(self):
        return self.lgbm.encoder

    @property
    def prior(self) -> float:
        return self.lgbm.prior

    def features(self, df: pd.DataFrame) -> pd.DataFrame:
        return self.lgbm.features(df)

    def predict(self, X: pd.DataFrame) -> dict[str, np.ndarray]:
        """score = ranking score of the primary model; p = probability shown for the primary model."""
        raw = self.lgbm.raw(X)
        out = {"lgbm_raw": raw, "lgbm_p": self.lgbm.calibrate(raw)}
        out["ebm_p"] = self.ebm.predict_proba(X)[:, 1] if self.ebm is not None else np.full(len(X), np.nan)
        if self.primary == "ebm" and self.ebm is not None:
            out["score"], out["p"] = out["ebm_p"], out["ebm_p"]
        else:
            out["score"], out["p"] = raw, out["lgbm_p"]
        return out

    def contributions(self, X: pd.DataFrame, model: str | None = None):
        model = model or self.primary
        if model == "ebm" and self.ebm is not None:
            return ebm_group_contributions(self.ebm, X)
        return lgbm_group_contributions(self.lgbm, X)

    @property
    def primary_label(self) -> str:
        return MODEL_LABELS[self.primary]


def choose_primary(m_lgbm: dict, m_ebm: dict, target: str) -> str:
    k = OPERATING_METRIC[target]
    return "ebm" if m_ebm[k] >= m_lgbm[k] - MARGIN else "lightgbm"


def save_primary(primary: dict[str, str]) -> None:
    PRIMARY_FILE.write_text(json.dumps({**primary, "rule": PRIMARY_RULE}, indent=2), encoding="utf-8")


def load_primary() -> dict:
    if PRIMARY_FILE.exists():
        return json.loads(PRIMARY_FILE.read_text(encoding="utf-8"))
    return {t: "lightgbm" for t in C.TARGETS} | {"rule": PRIMARY_RULE}


def load_twins() -> dict[str, Twin]:
    prim = load_primary()
    out = {}
    for t in C.TARGETS:
        lgbm = TargetModel.load(t)
        path = C.MODELS_DIR / f"{t}_ebm.joblib"
        ebm = joblib.load(path) if path.exists() else None
        out[t] = Twin(t, lgbm, ebm, prim.get(t, "lightgbm") if ebm is not None else "lightgbm")
    return out
