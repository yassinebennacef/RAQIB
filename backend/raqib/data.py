"""Loaders for the public customs declarations dataset and HS product names.

`python -m raqib.data --download` clones both public datasets into data/raw/.
`python -m raqib.data` prints and writes the data card (artifacts/data_card.json).
"""
from __future__ import annotations

import argparse
import json
import subprocess
from functools import lru_cache

import numpy as np
import pandas as pd

from . import config as C

STR_COLS = [
    "Process Type", "Declarant ID", "Importer ID", "Seller ID", "Courier ID",
    "Country of Departure", "Country of Origin", "Tax Type", "Country of Origin Indicator",
]


def download() -> None:
    """Shallow-clone both public datasets (idempotent)."""
    C.DATA_RAW.mkdir(parents=True, exist_ok=True)
    for url, dest in [(C.CUSTOMS_URL, C.CUSTOMS_REPO), (C.HS_URL, C.HS_REPO)]:
        if dest.exists():
            print(f"[data] {dest.relative_to(C.ROOT)} already present")
            continue
        print(f"[data] cloning {url}")
        subprocess.run(["git", "clone", "--depth", "1", url, str(dest)], check=True)


def data_available() -> bool:
    return all((C.CUSTOMS_DIR / f).exists() for f in C.TRAIN_FILES + C.TEST_FILES) and C.HS_CSV.exists()


def _read(files: list[str], split: str) -> pd.DataFrame:
    frames = []
    for f in files:
        # keep_default_na=False: country code "NA" (Namibia) must stay a string
        df = pd.read_csv(
            C.CUSTOMS_DIR / f,
            dtype={c: str for c in STR_COLS},
            keep_default_na=False,
            na_values={"Courier ID": [""], "Net Mass": [""], "Item Price": [""], "Tax Rate": [""]},
        )
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"])
    df["HS6 Code"] = df["HS6 Code"].astype(int)
    df["hs4"] = df["HS6 Code"] // 100
    df["hs2"] = df["HS6 Code"] // 10000
    df["unit"] = np.log1p(df["Item Price"] / np.maximum(df["Net Mass"], 0.1))
    df["fraud"] = df["Fraud"].astype(int)
    df["critical"] = (df["Critical Fraud"] == 2).astype(int)
    df["split"] = split
    return df


@lru_cache(maxsize=1)
def load_train() -> pd.DataFrame:
    """TRAIN = train + valid files (2020-01-01 .. 2021-03-31)."""
    return _read(C.TRAIN_FILES, "train")


@lru_cache(maxsize=1)
def load_test() -> pd.DataFrame:
    """TEST = test file (2021-04-01 .. 2021-06-30)."""
    return _read(C.TEST_FILES, "test")


@lru_cache(maxsize=1)
def hs_table() -> dict[str, str]:
    """hscode string (2, 4 or 6 digits) -> description."""
    hs = pd.read_csv(C.HS_CSV, dtype=str, keep_default_na=False)
    return dict(zip(hs["hscode"], hs["description"]))


def hs6_str(code) -> str:
    return str(int(code)).zfill(6)


def hs_description(code) -> str:
    """HS6 description, falling back to the 4-digit heading, then 'HS <code>'."""
    table = hs_table()
    s = hs6_str(code)
    if s in table:
        return table[s]
    if s[:4] in table:
        return table[s[:4]]
    return f"HS {s}"


def hs_match_level(code) -> int:
    table = hs_table()
    s = hs6_str(code)
    if s in table:
        return 6
    if s[:4] in table:
        return 4
    return 0


def hs4_description(hs4) -> str:
    s = str(int(hs4)).zfill(4)
    return hs_table().get(s, f"HS {s}")


def hs2_description(hs2) -> str:
    s = str(int(hs2)).zfill(2)
    return hs_table().get(s, f"HS {s}")


def _split_card(df: pd.DataFrame) -> dict:
    return {
        "rows": int(len(df)),
        "period": [str(df["Date"].min().date()), str(df["Date"].max().date())],
        "days": int(df["Date"].nunique()),
        "fraud_rate": float(df["fraud"].mean()),
        "critical_rate": float(df["critical"].mean()),
        "n_fraud": int(df["fraud"].sum()),
        "n_critical": int(df["critical"].sum()),
    }


def data_card() -> dict:
    train, test = load_train(), load_test()
    full = pd.concat([train, test], ignore_index=True)
    levels = full["HS6 Code"].map(hs_match_level)
    card = {
        "dataset": "Customs Import Declaration Datasets (synthetic, CTGAN) - IBS & Korea Customs Service",
        "licence": "MIT",
        "source_url": C.CUSTOMS_URL,
        "hs_names": {"source_url": C.HS_URL, "licence": "ODC-PDDL-1.0"},
        "rows": int(len(full)),
        "columns": 22,
        "train": _split_card(train),
        "test": _split_card(test),
        "unique": {
            "importers": int(full["Importer ID"].nunique()),
            "declarants": int(full["Declarant ID"].nunique()),
            "sellers": int(full["Seller ID"].nunique()),
            "hs6": int(full["HS6 Code"].nunique()),
            "origins": int(full["Country of Origin"].nunique()),
            "offices": int(full["Office ID"].nunique()),
        },
        "fraud_rate": float(full["fraud"].mean()),
        "critical_rate": float(full["critical"].mean()),
        "hs_name_match": {
            "hs6": float((levels == 6).mean()),
            "hs4_fallback": float((levels == 4).mean()),
            "none": float((levels == 0).mean()),
        },
        "test_new_operators": {
            "importer": float((~test["Importer ID"].isin(set(train["Importer ID"]))).mean()),
            "declarant": float((~test["Declarant ID"].isin(set(train["Declarant ID"]))).mean()),
            "seller": float((~test["Seller ID"].isin(set(train["Seller ID"]))).mean()),
            "hs6": float((~test["HS6 Code"].isin(set(train["HS6 Code"]))).mean()),
        },
        "notes": [
            "Only inspected (labelled) declarations were synthesised, so the fraud rate is far "
            "higher than among all declarations; the gain over the rule is the claim, not the "
            "absolute precision.",
            "Item price is the assessed value in KRW; net mass in kg.",
        ],
    }
    return card


def write_data_card() -> dict:
    card = data_card()
    C.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (C.ARTIFACTS / "data_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    return card


def main() -> None:
    ap = argparse.ArgumentParser(description="RAQIB data utilities")
    ap.add_argument("--download", action="store_true", help="clone the public datasets into data/raw")
    args = ap.parse_args()
    if args.download or not data_available():
        download()
    card = write_data_card()
    print(json.dumps(card, indent=2))


if __name__ == "__main__":
    main()
