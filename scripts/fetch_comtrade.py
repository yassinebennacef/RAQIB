"""Download Tunisia's public import statistics from UN Comtrade (keyless preview API).

Run once, with network:  .venv/Scripts/python scripts/fetch_comtrade.py
Saves the raw JSON answers in data/public_tn/ (committed); the app never calls the API at run time.
Then `python -m raqib.tunisia` builds artifacts/tunisia_ref.json from these files.

Source: UN Comtrade Database, https://comtradeplus.un.org (public preview API, one period per call,
1 s pause between calls). Reporter 788 = Tunisia.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "public_tn"
BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
TUNISIA = 788
NOT_COUNTRIES = {0, 97, 290, 492, 527, 568, 577, 636, 637, 837, 838, 839, 849, 879, 899}  # World, areas nes...


AGGREGATE = {"motCode": 0, "customsCode": "C00", "partner2Code": 0}  # totals only (some reporters split by mode)


def get(params: dict, name: str) -> dict:
    params = {**params, **AGGREGATE}
    url = BASE + "?" + urllib.parse.urlencode(params, safe=",")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            break
        except Exception as exc:  # network hiccup or rate limit: wait and retry
            print(f"  retry {attempt + 1} {name}: {exc}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    else:
        raise SystemExit(f"UN Comtrade unreachable for {name}")
    time.sleep(1.0)
    payload = {"url": url, "fetched": date.today().isoformat(), "params": params, "count": data.get("count"),
               "error": data.get("error"), "data": data.get("data") or []}
    (OUT / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"{name}: {payload['count']} rows")
    return payload


def refetch_split() -> None:
    """Re-download the saved answers that were split by transport mode or truncated at 500 rows."""
    for f in sorted(OUT.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if "params" not in d:
            continue
        if d.get("count") == 500 or any(r.get("motCode") not in (0, None) for r in d["data"]):
            get(d["params"], f.stem)


def main() -> None:
    if "--refetch-split" in sys.argv:
        return refetch_split()
    OUT.mkdir(parents=True, exist_ok=True)
    year = None
    for y in (2024, 2023):
        p = get({"reporterCode": TUNISIA, "flowCode": "M", "period": y, "partnerCode": 0, "cmdCode": "TOTAL"},
                f"tn_imports_total_{y}")
        if p["data"]:
            year = y
            break
    if year is None:
        raise SystemExit("No Tunisian import data for 2024 or 2023")

    # (a) imports by HS2 chapter, partner = World
    get({"reporterCode": TUNISIA, "flowCode": "M", "period": year, "partnerCode": 0, "cmdCode": "AG2"},
        f"tn_imports_hs2_{year}")
    # imports by partner (all goods) -> top origins and mirror partners
    by_partner = get({"reporterCode": TUNISIA, "flowCode": "M", "period": year, "cmdCode": "TOTAL"},
                     f"tn_imports_partners_{year}")

    # (b) imports by HS6 for the HS6 codes of the test set
    test = pd.read_parquet(ROOT / "artifacts" / "test_scored.parquet", columns=["hs6"])
    codes = sorted({str(c).zfill(6) for c in test["hs6"].unique()})
    for i in range(0, len(codes), 40):
        get({"reporterCode": TUNISIA, "flowCode": "M", "period": year, "partnerCode": 0,
             "cmdCode": ",".join(codes[i:i + 40])}, f"tn_imports_hs6_{year}_{i // 40:03d}")

    # (c) mirror data: top 10 partners' exports to Tunisia vs Tunisia's imports from them, HS2 level
    rows = [r for r in by_partner["data"] if r["partnerCode"] not in NOT_COUNTRIES and r.get("primaryValue")]
    top = sorted(rows, key=lambda r: -r["primaryValue"])[:10]
    for r in top:
        pc = r["partnerCode"]
        get({"reporterCode": TUNISIA, "flowCode": "M", "period": year, "partnerCode": pc, "cmdCode": "AG2"},
            f"mirror_tn_m_{pc}_{year}")
        get({"reporterCode": pc, "flowCode": "X", "period": year, "partnerCode": TUNISIA, "cmdCode": "AG2"},
            f"mirror_partner_x_{pc}_{year}")
    (OUT / "manifest.json").write_text(json.dumps({"year": year, "fetched": date.today().isoformat(),
                                                   "mirror_partners": [r["partnerCode"] for r in top],
                                                   "hs6_codes": len(codes)}, indent=1), encoding="utf-8")
    print("done, year", year)


if __name__ == "__main__":
    main()
