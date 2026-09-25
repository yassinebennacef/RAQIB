"""Paths and recipe constants shared by the whole pipeline."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
CUSTOMS_REPO = DATA_RAW / "customs"
CUSTOMS_DIR = CUSTOMS_REPO / "data"
HS_REPO = DATA_RAW / "hs"
HS_CSV = HS_REPO / "data" / "harmonized-system.csv"
ARTIFACTS = ROOT / "artifacts"
MODELS_DIR = ARTIFACTS / "models"
FRONTEND_DIST = ROOT / "frontend" / "dist"
DECISIONS_LOG = ARTIFACTS / "decisions.jsonl"

CUSTOMS_URL = "https://github.com/Seondong/Customs-Declaration-Datasets"
HS_URL = "https://github.com/datasets/harmonized-system"

TRAIN_FILES = ["df_syn_train_eng.csv", "df_syn_valid_eng.csv"]
TEST_FILES = ["df_syn_test_eng.csv"]

# target name -> smoothing strength a
TARGETS: dict[str, float] = {"fraud": 10.0, "critical": 20.0}

# (source column, short name) for every target-encoded key
KEYS: list[tuple[str, str]] = [
    ("HS6 Code", "hs6"),
    ("hs4", "hs4"),
    ("hs2", "hs2"),
    ("Importer ID", "importer"),
    ("Declarant ID", "declarant"),
    ("Seller ID", "seller"),
    ("Country of Origin", "origin"),
    ("Office ID", "office"),
]

# (source column, feature name) for the numeric features
NUMERIC: list[tuple[str, str]] = [
    ("Tax Rate", "tax_rate"),
    ("Net Mass", "net_mass"),
    ("Item Price", "item_price"),
    ("unit", "unit"),
]

FEATURES: list[str] = (
    [f"rate_{k}" for _, k in KEYS]
    + [f"count_{k}" for _, k in KEYS]
    + [f for _, f in NUMERIC]
)

LGBM_PARAMS = dict(
    n_estimators=300,
    learning_rate=0.03,
    num_leaves=15,
    min_child_samples=100,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.8,
    random_state=42,
    verbose=-1,
)

ENCODING_FOLDS_SEED = 0
CALIBRATION_FOLDS_SEED = 1
N_FOLDS = 5

# Operating points
DEFAULT_RATE = 0.05          # daily inspection capacity (share of declarations)
DEFAULT_EXPLORE = 0.10       # exploration share used by the "ai_explore" policy
ALERT_QUANTILE = 0.99        # public-safety alert: p_critical >= 99th pct of TEST
YELLOW_SHARE = 0.10          # document check: next 10% of the day by p_fraud
REPLAY_SEED = 7
THIN_HISTORY = 20            # "(thin history)" below this many past declarations

# Code labels documented in the dataset's EDA notebook (codes/EDA.ipynb)
TRANSPORT_LABELS = {10: "Maritime", 20: "Rail", 30: "Road", 40: "Air", 50: "Mail", 90: "Others"}
OFFICE_LABELS = {
    10: "Seoul Regional Customs",
    13: "Incheon Airport Intl. Postal Customs",
    16: "Pyeongtaek Customs",
    20: "Incheon Regional Customs (Port)",
    30: "Busan Regional Customs",
    40: "Incheon Regional Customs (Airport)",
}


def transport_label(code) -> str:
    try:
        return TRANSPORT_LABELS.get(int(code), f"Mode {code}")
    except (TypeError, ValueError):
        return f"Mode {code}"


def office_label(code) -> str:
    try:
        return OFFICE_LABELS.get(int(code), f"Office {code}")
    except (TypeError, ValueError):
        return f"Office {code}"
