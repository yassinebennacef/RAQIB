"""Real Tunisian public data (UN Comtrade, reporter 788) -> artifacts/tunisia_ref.json.

Information only: nothing here is fed into the models, the lanes or the replay.
Built offline from the raw answers saved in data/public_tn/ by scripts/fetch_comtrade.py.
Run: .venv/Scripts/python -m raqib.tunisia
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from . import currency
from .config import ARTIFACTS, ROOT

RAW_DIR = ROOT / "data" / "public_tn"
REF_FILE = ARTIFACTS / "tunisia_ref.json"
UNDER_THRESHOLD = 0.5  # declared value/kg below 50% of the Tunisian reference -> "sous-évaluation possible"
NOT_COUNTRIES = {0, 97, 290, 492, 527, 568, 577, 636, 637, 837, 838, 839, 849, 879, 899}


def _load(raw_dir: Path, name: str) -> list[dict]:
    p = raw_dir / f"{name}.json"
    rows = json.loads(p.read_text(encoding="utf-8"))["data"] if p.exists() else []
    return [r for r in rows if _aggregate(r)]


def _aggregate(r: dict) -> bool:
    """Keep only the total rows (all transport modes, all customs procedures, no second partner)."""
    return r.get("motCode", 0) == 0 and r.get("customsCode", "C00") == "C00" and r.get("partner2Code", 0) == 0


# French display names (labels only) for Tunisia's main partners, by ISO alpha-2
NAMES_FR = {"IT": "Italie", "CN": "Chine", "FR": "France", "DZ": "Algérie", "DE": "Allemagne", "RU": "Russie",
            "TR": "Turquie", "ES": "Espagne", "AZ": "Azerbaïdjan", "IN": "Inde", "US": "États-Unis",
            "BE": "Belgique", "NL": "Pays-Bas", "EG": "Égypte", "LY": "Libye", "UA": "Ukraine", "BR": "Brésil",
            "PT": "Portugal", "GB": "Royaume-Uni", "JP": "Japon", "KR": "Corée du Sud", "SA": "Arabie saoudite",
            "MA": "Maroc", "AR": "Argentine", "RO": "Roumanie", "PL": "Pologne", "CH": "Suisse", "AT": "Autriche",
            "CZ": "Tchéquie", "VN": "Viêt Nam", "TH": "Thaïlande", "MY": "Malaisie", "ID": "Indonésie",
            "SE": "Suède", "GR": "Grèce", "HU": "Hongrie", "SK": "Slovaquie", "CA": "Canada", "MX": "Mexique"}


def _partner_names(raw_dir: Path) -> dict[int, dict]:
    p = raw_dir / "ref_partnerAreas.json"
    if not p.exists():
        return {}
    rows = json.loads(p.read_text(encoding="utf-8-sig"))["results"]
    out = {}
    for r in rows:
        iso2 = r.get("PartnerCodeIsoAlpha2") or ""
        # the reference file carries U+FFFD for a few accented names
        name = r["PartnerDesc"].strip().replace("T�rkiye", "Türkiye").replace("�", "?")
        out[int(r["PartnerCode"])] = {"name": NAMES_FR.get(iso2, name), "name_en": name, "iso2": iso2}
    return out


def _hs_names() -> dict[str, str]:
    p = ARTIFACTS / "hs_names.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def build(raw_dir: Path = RAW_DIR, test: pd.DataFrame | None = None) -> dict:
    manifest = json.loads((raw_dir / "manifest.json").read_text(encoding="utf-8"))
    year = int(manifest["year"])
    names = _partner_names(raw_dir)
    hs = _hs_names()
    source = f"UN Comtrade (Tunisie, {year})"

    total = _load(raw_dir, f"tn_imports_total_{year}")
    total_usd = float(total[0]["primaryValue"]) if total else None

    chapters = sorted(({"hs2": r["cmdCode"], "label": hs.get(r["cmdCode"], f"Chapitre {r['cmdCode']}"),
                        "usd": float(r["primaryValue"])} for r in _load(raw_dir, f"tn_imports_hs2_{year}")
                       if r.get("primaryValue")), key=lambda r: -r["usd"])
    origins = sorted(({"code": int(r["partnerCode"]), **names.get(int(r["partnerCode"]),
                                                               {"name": str(r["partnerCode"]), "iso2": ""}),
                       "usd": float(r["primaryValue"])} for r in _load(raw_dir, f"tn_imports_partners_{year}")
                      if r.get("primaryValue") and int(r["partnerCode"]) not in NOT_COUNTRIES),
                     key=lambda r: -r["usd"])

    # Tunisian reference unit value per HS6 = primaryValue / netWgt (CIF, USD per kg)
    hs6: dict[str, dict] = {}
    for f in sorted(raw_dir.glob(f"tn_imports_hs6_{year}_*.json")):
        for r in filter(_aggregate, json.loads(f.read_text(encoding="utf-8"))["data"]):
            v, w = r.get("primaryValue"), r.get("netWgt")
            if v and w and w > 0:
                hs6[str(r["cmdCode"]).zfill(6)] = {"usd": float(v), "kg": float(w), "usd_per_kg": float(v) / float(w)}

    # Mirror gap per partner x HS2 = (Tunisia's imports - partner's exports to Tunisia) / partner's exports
    mirror = []
    for pc in manifest.get("mirror_partners", []):
        m = {r["cmdCode"]: float(r["primaryValue"]) for r in _load(raw_dir, f"mirror_tn_m_{pc}_{year}")
             if r.get("primaryValue")}
        x = {r["cmdCode"]: float(r["primaryValue"]) for r in _load(raw_dir, f"mirror_partner_x_{pc}_{year}")
             if r.get("primaryValue")}
        info = names.get(int(pc), {"name": str(pc), "iso2": ""})
        if not x:
            mirror.append({"code": int(pc), **info, "reported": False, "tn_imports_usd": sum(m.values()),
                           "partner_exports_usd": None, "gap": None, "chapters": []})
            continue
        chs = []
        for c in sorted(set(m) | set(x)):
            if x.get(c, 0) > 0 and c in m:
                chs.append({"hs2": c, "label": hs.get(c, c), "tn_imports_usd": m[c], "partner_exports_usd": x[c],
                            "gap": (m[c] - x[c]) / x[c]})
        chs.sort(key=lambda r: -r["partner_exports_usd"])
        tm, tx = sum(m.values()), sum(x.values())
        mirror.append({"code": int(pc), **info, "reported": True, "tn_imports_usd": tm, "partner_exports_usd": tx,
                       "gap": (tm - tx) / tx if tx else None, "chapters": chs[:10]})

    ref = {
        "source": source, "year": year, "fetched": manifest.get("fetched"),
        "url": "https://comtradeplus.un.org", "api": "https://comtradeapi.un.org/public/v1/preview/C/A/HS",
        "reporter": {"code": 788, "name": "Tunisia"},
        "total_imports_usd": total_usd, "top_chapters": chapters[:15], "top_origins": origins[:15],
        "hs6_ref": hs6, "mirror": mirror,
        "caveat_mirror": ("Importations tunisiennes déclarées CIF, exportations des partenaires FOB : un écart "
                          "positif de ~5 à 10 % est normal (fret + assurance). Écart miroir : indicateur reconnu "
                          "de sous-facturation, pas une preuve."),
        "threshold": UNDER_THRESHOLD,
    }
    ref["check"] = red_green_check(ref, test)
    return ref


def ref_gap(ref: dict, hs6: str, item_price_krw: float, net_mass: float) -> dict | None:
    """Declared value/kg vs the Tunisian reference for this HS6, both in USD/kg; None when no reference."""
    r = ref["hs6_ref"].get(str(hs6).zfill(6))
    if not r or net_mass is None or float(net_mass) <= 0:
        return None
    declared_usd_kg = currency.to_usd(float(item_price_krw), "krw") / max(float(net_mass), 0.1)
    ratio = declared_usd_kg / r["usd_per_kg"]
    return {"hs6": str(hs6).zfill(6), "declared_usd_per_kg": declared_usd_kg, "ref_usd_per_kg": r["usd_per_kg"],
            "ratio": ratio, "gap": ratio - 1.0, "under": bool(ratio < ref.get("threshold", UNDER_THRESHOLD)),
            "year": ref["year"], "source": ref["source"]}


def red_green_check(ref: dict, test: pd.DataFrame | None) -> dict | None:
    """Share of RED vs GREEN lanes whose declared value/kg is below 50% of the Tunisian reference."""
    if test is None:
        p = ARTIFACTS / "test_scored.parquet"
        if not p.exists():
            return None
        test = pd.read_parquet(p, columns=["hs6", "item_price", "net_mass", "lane", "fraud"])
    t = test.copy()
    t["hs6"] = t["hs6"].astype(str).str.zfill(6)
    refv = t["hs6"].map({k: v["usd_per_kg"] for k, v in ref["hs6_ref"].items()})
    declared = t["item_price"].astype(float) / currency.rates()["krw_per_usd"] / np.maximum(t["net_mass"].astype(float), 0.1)
    t["has_ref"] = refv.notna() & (t["net_mass"].astype(float) > 0)
    t["under"] = t["has_ref"] & (declared < UNDER_THRESHOLD * refv)
    out = {}
    for lane in ("RED", "YELLOW", "GREEN"):
        s = t[t["lane"] == lane]
        n_ref = int(s["has_ref"].sum())
        out[lane] = {"n": int(len(s)), "with_ref": n_ref, "under": int(s["under"].sum()),
                     "share_under": float(s["under"].sum() / n_ref) if n_ref else None}
    if "fraud" in t:
        for k, s in (("fraud", t[t["fraud"] == 1]), ("no_fraud", t[t["fraud"] == 0])):
            n_ref = int(s["has_ref"].sum())
            out[k] = {"n": int(len(s)), "with_ref": n_ref, "under": int(s["under"].sum()),
                      "share_under": float(s["under"].sum() / n_ref) if n_ref else None}
    out["coverage"] = float(t["has_ref"].mean())
    ratio = (declared / refv)[t["has_ref"]]
    out["median_ratio"] = float(ratio.median()) if len(ratio) else None
    out["median_ratio_by_lane"] = {lane: float(ratio[t.loc[ratio.index, "lane"] == lane].median())
                                   for lane in ("RED", "YELLOW", "GREEN") if (t.loc[ratio.index, "lane"] == lane).any()}
    out["share_under_all"] = float(t["under"].sum() / max(int(t["has_ref"].sum()), 1))
    out["caveat"] = "données de déclaration synthétiques coréennes × prix de référence réels tunisiens"
    return out


@lru_cache(maxsize=1)
def load() -> dict | None:
    """artifacts/tunisia_ref.json, rebuilt from data/public_tn when missing (never calls the network)."""
    if REF_FILE.exists():
        return json.loads(REF_FILE.read_text(encoding="utf-8"))
    if (RAW_DIR / "manifest.json").exists():
        ref = build()
        REF_FILE.parent.mkdir(parents=True, exist_ok=True)
        REF_FILE.write_text(json.dumps(ref, ensure_ascii=False), encoding="utf-8")
        return ref
    return None


def main() -> None:
    ref = build()
    REF_FILE.write_text(json.dumps(ref, ensure_ascii=False), encoding="utf-8")
    c = ref["check"] or {}
    print(f"{ref['source']}: {len(ref['hs6_ref'])} HS6 references, {len(ref['mirror'])} mirror partners")
    for k in ("RED", "YELLOW", "GREEN", "fraud", "no_fraud"):
        if k in c:
            print(k, c[k])
    print("coverage", c.get("coverage"))


if __name__ == "__main__":
    main()
