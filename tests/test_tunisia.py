"""Tunisian edition: currency conversion, French formatting, UN Comtrade reference built from saved files.

No network: urllib is blocked for the whole module.
"""
import json
import urllib.request

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from raqib import currency as CUR
from raqib import tunisia as TN


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network call during tests")
    monkeypatch.setattr(urllib.request, "urlopen", boom)


# ---------------------------------------------------------------- currency
def test_reference_rates():
    r = CUR.rates()
    assert r["tnd_per_eur"] == 3.3701 and r["tnd_per_usd"] == 2.9508
    assert r["reference_date"] == "2026-09-23"
    # FRED EXKOUS monthly mean Jan 2020 - Jun 2021 (saved CSV), close to the ~1160 of the brief
    assert 1150 < r["krw_per_usd"] < 1170


@pytest.mark.parametrize("cur", ["tnd", "eur", "usd"])
def test_round_trip(cur):
    for usd in (0.01, 1.0, 1234.56, 9.9e8):
        m = CUR.usd_to(usd)
        assert CUR.to_usd(m[cur], cur) == pytest.approx(usd, rel=1e-12)
    krw = 1_160_000.0
    assert CUR.to_usd(CUR.krw_to(krw)["tnd"], "tnd") == pytest.approx(CUR.to_usd(krw, "krw"), rel=1e-12)


def test_cross_rates():
    m = CUR.usd_to(100.0)
    assert m["tnd"] == pytest.approx(295.08)
    assert m["eur"] == pytest.approx(295.08 / 3.3701)
    assert CUR.money(CUR.rates()["krw_per_usd"])["usd"] == pytest.approx(1.0)
    assert CUR.per_kg(1000.0, 0.0) == CUR.money(1000.0 / 0.1, 4)  # mass floored at 0.1 kg like the model


def test_french_format():
    nb = " "
    assert CUR.fmt_fr(12345.67, "tnd") == f"12{nb}345,67 TND"
    assert CUR.fmt_fr(0.5, "eur") == "0,50 EUR"
    assert CUR.fmt_fr(-1234567.891, "usd") == f"-1{nb}234{nb}567,89 USD"


def test_rates_override(tmp_path, monkeypatch):
    f = tmp_path / "rates.json"
    f.write_text(json.dumps({"tnd_per_usd": 3.0, "reference_date": "2030-01-01"}), encoding="utf-8")
    monkeypatch.setattr(CUR, "RATES_FILE", f)
    CUR.rates.cache_clear()
    try:
        assert CUR.usd_to(1.0)["tnd"] == 3.0 and CUR.rates()["reference_date"] == "2030-01-01"
    finally:
        CUR.rates.cache_clear()


# ---------------------------------------------------------------- UN Comtrade reference (saved files)
def _write(d, name, rows):
    (d / f"{name}.json").write_text(json.dumps({"data": rows}), encoding="utf-8")


def _row(cmd, value, partner=0, wgt=None, mot=0):
    return {"cmdCode": cmd, "primaryValue": value, "netWgt": wgt, "partnerCode": partner, "motCode": mot,
            "customsCode": "C00", "partner2Code": 0}


def test_build_from_saved_files(tmp_path):
    d = tmp_path
    (d / "manifest.json").write_text(json.dumps({"year": 2024, "fetched": "2026-09-26", "mirror_partners": [380, 643]}))
    (d / "ref_partnerAreas.json").write_text(json.dumps({"results": [
        {"PartnerCode": 380, "PartnerDesc": "Italy", "PartnerCodeIsoAlpha2": "IT"},
        {"PartnerCode": 643, "PartnerDesc": "Russian Federation", "PartnerCodeIsoAlpha2": "RU"}]}))
    _write(d, "tn_imports_total_2024", [_row("TOTAL", 1000.0)])
    _write(d, "tn_imports_hs2_2024", [_row("27", 600.0), _row("85", 400.0)])
    _write(d, "tn_imports_partners_2024", [_row("TOTAL", 700.0, 380), _row("TOTAL", 300.0, 643), _row("TOTAL", 1000.0, 0)])
    _write(d, "tn_imports_hs6_2024_000", [_row("711311", 5000.0, wgt=10.0), _row("420231", 100.0, wgt=None)])
    # partner rows split by transport mode must be ignored (only motCode 0 totals count)
    _write(d, "mirror_tn_m_380_2024", [_row("27", 110.0, 380), _row("85", 50.0, 380)])
    _write(d, "mirror_partner_x_380_2024", [_row("27", 100.0, 380), _row("27", 60.0, 380, mot=2100),
                                            _row("85", 100.0, 380)])
    _write(d, "mirror_tn_m_643_2024", [_row("27", 300.0, 643)])
    _write(d, "mirror_partner_x_643_2024", [])
    krw = CUR.rates()["krw_per_usd"]
    test = pd.DataFrame({"hs6": [711311, 711311, 420231], "item_price": [100 * krw, 400 * krw, 1.0],
                         "net_mass": [1.0, 1.0, 1.0], "lane": ["RED", "GREEN", "GREEN"], "fraud": [1, 0, 0]})
    ref = TN.build(d, test)
    assert ref["year"] == 2024 and ref["source"] == "UN Comtrade (Tunisie, 2024)"
    assert ref["hs6_ref"] == {"711311": {"usd": 5000.0, "kg": 10.0, "usd_per_kg": 500.0}}  # no weight -> no ref
    assert [c["hs2"] for c in ref["top_chapters"]] == ["27", "85"]
    assert [o["name"] for o in ref["top_origins"]] == ["Italie", "Russie"]  # World (0) excluded
    it, ru = ref["mirror"]
    assert it["gap"] == pytest.approx((160 - 200) / 200)
    assert next(c for c in it["chapters"] if c["hs2"] == "27")["gap"] == pytest.approx(0.1)
    assert ru["reported"] is False and ru["gap"] is None
    # declared 100 USD/kg vs 500 USD/kg reference -> ratio 0.2 -> under; 400/500 = 0.8 -> not under
    g = TN.ref_gap(ref, "711311", 100 * krw, 1.0)
    assert g["ratio"] == pytest.approx(0.2) and g["under"] is True
    assert TN.ref_gap(ref, "711311", 400 * krw, 1.0)["under"] is False
    assert TN.ref_gap(ref, "420231", 1.0, 1.0) is None
    c = ref["check"]
    assert c["RED"] == {"n": 1, "with_ref": 1, "under": 1, "share_under": 1.0}
    assert c["GREEN"]["with_ref"] == 1 and c["GREEN"]["share_under"] == 0.0
    assert c["coverage"] == pytest.approx(2 / 3)


def test_saved_public_data_loads_offline():
    """The committed raw files in data/public_tn rebuild the reference without any network call."""
    if not (TN.RAW_DIR / "manifest.json").exists():
        pytest.skip("data/public_tn not downloaded")
    ref = TN.build(TN.RAW_DIR, pd.DataFrame({"hs6": [], "item_price": [], "net_mass": [], "lane": [], "fraud": []}))
    assert ref["year"] in (2023, 2024)
    assert ref["total_imports_usd"] > 1e10  # Tunisia imports > 10 bn USD a year
    assert len(ref["hs6_ref"]) > 500 and len(ref["top_chapters"]) == 15 and len(ref["top_origins"]) == 15
    assert all(v["usd_per_kg"] > 0 for v in ref["hs6_ref"].values())
    reported = [m for m in ref["mirror"] if m["reported"]]
    assert reported and all(-1 < m["gap"] < 5 for m in reported)


# ---------------------------------------------------------------- API
@pytest.fixture(scope="module")
def client(built):
    from raqib.api import app
    with TestClient(app) as c:
        yield c


def test_api_currency_and_money_fields(client):
    r = client.get("/api/currency").json()
    assert r["default"] == "tnd" and r["tnd_per_eur"] == 3.3701
    wl = client.get("/api/worklist?page_size=5").json()
    it = wl["items"][0]
    assert set(it["value"]) == {"tnd", "eur", "usd"} and set(it["value_per_kg"]) == {"tnd", "eur", "usd"}
    assert it["value"]["usd"] == pytest.approx(it["item_price"] / CUR.rates()["krw_per_usd"], abs=0.01)
    d = client.get(f"/api/declaration/{it['id']}").json()
    assert set(d["declaration"]["value"]) == {"tnd", "eur", "usd"}
    assert "available" in d["tunisia_ref"]


def test_api_tunisia_and_duties(client):
    if TN.load() is None:
        pytest.skip("no Tunisian reference")
    t = client.get("/api/tunisia").json()
    assert t["source"].startswith("UN Comtrade (Tunisie") and len(t["top_chapters"]) == 15
    d = client.get("/api/tunisia/duties?rate=0.05").json()
    p = d["policies"]
    # frauds caught at 5% equal the replay numbers (317 / 259 / 103)
    assert (p["ai"]["frauds_caught"], p["rule"]["frauds_caught"], p["random"]["frauds_caught"]) == (317, 259, 103)
    assert p["ai"]["total"]["tnd"] > 0 and d["vat_rate"] == 0.19
