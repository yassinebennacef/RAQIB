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


# ------------------------------------------------------------------------------ glass-box twin (EBM)
EBM_PARAMS = dict(interactions=5, outer_bags=4, random_state=42, n_jobs=4)  # 4 bags -> 4 workers (memory-safe)
EBM_SHADOW_PARAMS = dict(interactions=5, outer_bags=2, random_state=42, n_jobs=2)


def _cache_key(name: str, X: pd.DataFrame, y, params: dict) -> str:
    import hashlib
    import json as _json

    h = hashlib.sha256()
    h.update(name.encode())
    h.update(_json.dumps(params, sort_keys=True).encode())
    h.update(",".join(X.columns).encode())
    h.update(pd.util.hash_pandas_object(X, index=False).to_numpy().tobytes())
    h.update(np.asarray(y, dtype=np.int64).tobytes())
    return h.hexdigest()[:20]


def fit_ebm_cached(name: str, X: pd.DataFrame, y, params: dict | None = None):
    """Fit an ExplainableBoostingClassifier once; reuse it while features, labels and params are unchanged."""
    import json as _json
    import time as _time

    from interpret.glassbox import ExplainableBoostingClassifier

    params = params or EBM_PARAMS
    C.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    path = C.MODELS_DIR / f"{name}_ebm.joblib"
    meta = C.MODELS_DIR / f"{name}_ebm.json"
    key = _cache_key(name, X, y, params)
    if path.exists() and meta.exists():
        info = _json.loads(meta.read_text(encoding="utf-8"))
        if info.get("key") == key:
            return joblib.load(path), info
    t0 = _time.time()
    ebm = ExplainableBoostingClassifier(**params).fit(X, np.asarray(y, dtype=int))
    info = {"key": key, "params": params, "fit_seconds": round(_time.time() - t0, 1), "rows": int(len(X))}
    joblib.dump(ebm, path)
    meta.write_text(_json.dumps(info, indent=2), encoding="utf-8")
    return ebm, info


def shadow_split(train: pd.DataFrame, weeks: int = 4) -> tuple[pd.DataFrame, pd.DataFrame]:
    """TRAIN minus its last `weeks` weeks, and those last weeks (for out-of-sample thresholds)."""
    cut = train["Date"].max() - pd.Timedelta(days=7 * weeks - 1)
    return train[train["Date"] < cut], train[train["Date"] >= cut]


def fit_shadow_pair(train: pd.DataFrame, target: str = "fraud") -> dict:
    """LightGBM + EBM trained without the last 4 TRAIN weeks; their raw probabilities on those weeks."""
    early, late = shadow_split(train)
    y_e = early[target].to_numpy(int)
    a = C.TARGETS[target]
    prior = float(y_e.mean())
    X_e = build_X(oof_encode(early, y_e, a, prior), early)
    enc = TargetEncoder.fit(early, y_e, a, prior)
    X_l = build_X(enc.transform(late), late)
    lgbm = LGBMClassifier(**C.LGBM_PARAMS).fit(X_e, y_e)
    ebm, info = fit_ebm_cached(f"{target}_shadow", X_e, y_e, EBM_SHADOW_PARAMS)
    return {"p_lgbm": lgbm.predict_proba(X_l)[:, 1], "p_ebm": ebm.predict_proba(X_l)[:, 1],
            "n_late": int(len(late)), "late_period": [str(late["Date"].min().date()), str(late["Date"].max().date())],
            "fit": info}
