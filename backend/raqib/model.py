"""Duty-fraud and critical-fraud models.

Recipe (one model per target; fraud a=10, critical a=20):
- target encoding of 8 keys: rate = (sum + a*prior) / (count + a) and count,
  computed OUT-OF-FOLD on TRAIN (KFold 5, shuffle, seed 0); TEST and new
  declarations use full-TRAIN statistics;
- numeric features: tax rate, net mass, item price, unit = log1p(price / max(mass, 0.1));
- LightGBM with fixed parameters (config.LGBM_PARAMS);
- isotonic calibration fitted on out-of-fold TRAIN predictions (KFold 5, seed 1).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import KFold

from . import config as C

ENC_COLS = [f"rate_{k}" for _, k in C.KEYS] + [f"count_{k}" for _, k in C.KEYS]


@dataclass
class TargetEncoder:
    """Smoothed per-key target statistics (sum/count per key value, prior, a)."""

    a: float
    prior: float
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)

    @classmethod
    def fit(cls, df: pd.DataFrame, y, a: float, prior: float) -> "TargetEncoder":
        yy = pd.Series(np.asarray(y, dtype=float), index=df.index)
        tables = {name: yy.groupby(df[col]).agg(["sum", "count"]) for col, name in C.KEYS}
        return cls(a=float(a), prior=float(prior), tables=tables)

    def stats(self, df: pd.DataFrame, col: str, name: str) -> tuple[np.ndarray, np.ndarray]:
        """(sum, count) of past declarations for each row's key value (0, 0 if unseen)."""
        t = self.tables[name]
        s = df[col].map(t["sum"]).fillna(0.0).to_numpy(dtype=float)
        c = df[col].map(t["count"]).fillna(0.0).to_numpy(dtype=float)
        return s, c

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = {}
        for col, name in C.KEYS:
            s, c = self.stats(df, col, name)
            out[f"rate_{name}"] = (s + self.a * self.prior) / (c + self.a)
            out[f"count_{name}"] = c
        return pd.DataFrame(out, index=df.index)[ENC_COLS]


def numeric_features(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {feat: df[col].to_numpy(dtype=float) for col, feat in C.NUMERIC}, index=df.index
    )


def build_X(encoded: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([encoded, numeric_features(df)], axis=1)[C.FEATURES]


def oof_encode(df: pd.DataFrame, y: np.ndarray, a: float, prior: float) -> pd.DataFrame:
    """Out-of-fold encoding: each fold's statistics come only from the other 4 folds."""
    out = pd.DataFrame(np.nan, index=df.index, columns=ENC_COLS)
    kf = KFold(C.N_FOLDS, shuffle=True, random_state=C.ENCODING_FOLDS_SEED)
    for tr, va in kf.split(df):
        enc = TargetEncoder.fit(df.iloc[tr], y[tr], a, prior)
        out.iloc[va] = enc.transform(df.iloc[va]).to_numpy()
    return out.astype(float)


@dataclass
class TargetModel:
    target: str
    a: float
    prior: float
    encoder: TargetEncoder
    model: LGBMClassifier
    calibrator: IsotonicRegression

    def features(self, df: pd.DataFrame) -> pd.DataFrame:
        return build_X(self.encoder.transform(df), df)

    def raw(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X)[:, 1]

    def calibrate(self, raw: np.ndarray) -> np.ndarray:
        return np.clip(self.calibrator.predict(raw), 0.0, 1.0)

    # ---- persistence -------------------------------------------------------
    def save(self) -> None:
        C.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, C.MODELS_DIR / f"{self.target}_model.joblib")
        joblib.dump(self.calibrator, C.MODELS_DIR / f"{self.target}_calibrator.joblib")
        joblib.dump(
            {"a": self.a, "prior": self.prior, "tables": self.encoder.tables, "keys": C.KEYS},
            C.MODELS_DIR / f"{self.target}_encoding.joblib",
        )
        self.model.booster_.save_model(str(C.MODELS_DIR / f"{self.target}_lgbm.txt"))

    @classmethod
    def load(cls, target: str) -> "TargetModel":
        enc = joblib.load(C.MODELS_DIR / f"{target}_encoding.joblib")
        return cls(
            target=target,
            a=enc["a"],
            prior=enc["prior"],
            encoder=TargetEncoder(a=enc["a"], prior=enc["prior"], tables=enc["tables"]),
            model=joblib.load(C.MODELS_DIR / f"{target}_model.joblib"),
            calibrator=joblib.load(C.MODELS_DIR / f"{target}_calibrator.joblib"),
        )


def fit_target(train: pd.DataFrame, target: str) -> tuple[TargetModel, pd.DataFrame, np.ndarray]:
    """Fit the full recipe for one target. Returns the model, TRAIN features and OOF predictions."""
    y = train[target].to_numpy(dtype=int)
    a = C.TARGETS[target]
    prior = float(y.mean())
    X_tr = build_X(oof_encode(train, y, a, prior), train)

    oof = np.zeros(len(y))
    kf = KFold(C.N_FOLDS, shuffle=True, random_state=C.CALIBRATION_FOLDS_SEED)
    for tr, va in kf.split(X_tr):
        m = LGBMClassifier(**C.LGBM_PARAMS).fit(X_tr.iloc[tr], y[tr])
        oof[va] = m.predict_proba(X_tr.iloc[va])[:, 1]
    calibrator = IsotonicRegression(out_of_bounds="clip").fit(oof, y)

    model = LGBMClassifier(**C.LGBM_PARAMS).fit(X_tr, y)
    encoder = TargetEncoder.fit(train, y, a, prior)
    tm = TargetModel(target=target, a=a, prior=prior, encoder=encoder, model=model, calibrator=calibrator)
    return tm, X_tr, oof


def hs6_unit_context(train: pd.DataFrame) -> dict:
    """Typical unit value (KRW per kg) per HS6 in TRAIN, used in explanations."""
    uv = train["Item Price"] / np.maximum(train["Net Mass"], 0.1)
    med = uv.groupby(train["HS6 Code"]).median()
    return {"hs6_unit_median": med, "global_unit_median": float(uv.median())}
