"""Currencies: the public dataset's values are in Korean won (KRW, dataset README); RAQIB shows TND, EUR, USD.

KRW -> USD at the average rate over the data period (Jan 2020 - Jun 2021), then USD -> TND / EUR at the
reference rates below. Every rate carries its date and source; config/rates.json overrides any of them.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .config import ROOT

RATES_FILE = ROOT / "config" / "rates.json"
FRED_CSV = ROOT / "data" / "public_tn" / "fred_EXKOUS_2020-01_2021-06.csv"
CURRENCIES = ("tnd", "eur", "usd")
SYMBOL = {"tnd": "TND", "eur": "EUR", "usd": "USD"}

DEFAULTS: dict = {
    "tnd_per_eur": 3.3701,
    "tnd_per_usd": 2.9508,
    "reference_date": "2026-09-23",
    "reference_source": "countryeconomy.com (cours du dinar tunisien, 23/09/2026)",
    "krw_per_usd": 1160.0,
    "krw_period": "2020-01 / 2021-06",
    "krw_source": "valeur approchée (~1160 KRW/USD)",
}


def _fred_period_mean(path: Path) -> float | None:
    """Mean of the monthly KRW per USD rates (FRED EXKOUS, Federal Reserve H.10) saved in data/public_tn."""
    if not path.exists():
        return None
    vals = []
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split(",")
        if len(parts) == 2 and parts[1] not in ("", "."):
            vals.append(float(parts[1]))
    return sum(vals) / len(vals) if vals else None


@lru_cache(maxsize=1)
def rates() -> dict:
    r = dict(DEFAULTS)
    fred = _fred_period_mean(FRED_CSV)
    if fred:
        r["krw_per_usd"] = round(fred, 2)
        r["krw_source"] = ("FRED EXKOUS (Federal Reserve Board H.10), moyenne des 18 taux mensuels "
                           "janv. 2020 - juin 2021 ; moyennes annuelles AEXKOUS 2020 = 1180,56, 2021 = 1144,89")
    if RATES_FILE.exists():
        r.update(json.loads(RATES_FILE.read_text(encoding="utf-8")))
    r["eur_per_usd"] = r["tnd_per_usd"] / r["tnd_per_eur"]
    return r


def usd_to(usd: float) -> dict[str, float]:
    r = rates()
    usd = float(usd)
    return {"tnd": usd * r["tnd_per_usd"], "eur": usd * r["tnd_per_usd"] / r["tnd_per_eur"], "usd": usd}


def krw_to(krw: float) -> dict[str, float]:
    return usd_to(float(krw) / rates()["krw_per_usd"])


def to_usd(amount: float, currency: str) -> float:
    r = rates()
    c = currency.lower()
    if c == "usd":
        return float(amount)
    if c == "tnd":
        return float(amount) / r["tnd_per_usd"]
    if c == "eur":
        return float(amount) * r["tnd_per_eur"] / r["tnd_per_usd"]
    if c == "krw":
        return float(amount) / r["krw_per_usd"]
    raise ValueError(currency)


def money(krw: float, digits: int = 2) -> dict[str, float]:
    """A KRW amount of the dataset as {tnd, eur, usd}, rounded for the API."""
    return {k: round(v, digits) for k, v in krw_to(krw).items()}


def per_kg(krw: float, mass: float) -> dict[str, float]:
    return money(float(krw) / max(float(mass), 0.1), 4)


def fmt_fr(value: float, currency: str = "tnd", digits: int = 2) -> str:
    """French number format: '12 345,67 TND' (narrow no-break space as thousands separator)."""
    s = f"{abs(float(value)):,.{digits}f}".replace(",", " ").replace(".", ",")
    return f"{'-' if float(value) < 0 else ''}{s} {SYMBOL.get(currency.lower(), currency.upper())}"


def public() -> dict:
    """What the front end needs to convert and label amounts."""
    r = rates()
    return {k: r[k] for k in ("tnd_per_eur", "tnd_per_usd", "eur_per_usd", "krw_per_usd", "reference_date",
                              "reference_source", "krw_period", "krw_source")} | {"default": "tnd"}
