# Real public Tunisian data — sources

Everything in this folder is a raw answer from a public, keyless source, saved once so the app runs offline.
Nothing here comes from a Tunisian administration system or a .gov.tn site. Rebuild the derived file with
`python -m raqib.tunisia` (writes `artifacts/tunisia_ref.json`); re-download with `python scripts/fetch_comtrade.py`.

## UN Comtrade (United Nations Statistics Division)

- Database: UN Comtrade, https://comtradeplus.un.org — "Source: UN Comtrade Database".
- API used: public preview API (no key), `https://comtradeapi.un.org/public/v1/preview/C/A/HS`, one period per call,
  1 s pause between calls, totals only (`motCode=0`, `customsCode=C00`, `partner2Code=0`).
  Exact URL and download date of every answer are stored inside each JSON file (`url`, `fetched`).
- Reporter 788 = Tunisia. Year used: **2024** (latest year with Tunisian data at download time).
- Downloaded: 2026-09-26.
- Files:
  - `tn_imports_total_2024.json` — Tunisia's total imports (partner World).
  - `tn_imports_hs2_2024.json` — Tunisia's imports by HS2 chapter (partner World).
  - `tn_imports_partners_2024.json` — Tunisia's imports by partner (all goods).
  - `tn_imports_hs6_2024_*.json` — Tunisia's imports for the 1,664 HS6 codes of RAQIB's test set
    (`primaryValue` in USD, CIF; `netWgt` in kg).
  - `mirror_tn_m_<partner>_2024.json` / `mirror_partner_x_<partner>_2024.json` — Tunisia's imports from, and the
    partner's exports to Tunisia, by HS2, for Tunisia's top 10 origins (mirror statistics).
  - `ref_partnerAreas.json` — Comtrade partner code list (https://comtradeapi.un.org/files/v1/app/reference/partnerAreas.json).
- Terms of use: https://comtradeplus.un.org/TermsOfUse — public statistics used here for a non-commercial
  hackathon prototype, with attribution.
- Caveats: Tunisian imports are CIF, partners' exports FOB (a positive gap of about 5-10 % is normal); the Russian
  Federation had not published 2024 exports at download time; HS6 rows without a net weight give no reference price.

## Exchange rates

- TND per EUR = 3.3701 and TND per USD = 2.9508 — countryeconomy.com (https://countryeconomy.com/currencies/tunisia),
  rates of 23 September 2026. Editable in `config/rates.json`.
- KRW per USD = mean of the 18 monthly rates Jan 2020 - Jun 2021 (the dataset's period) of FRED series **EXKOUS**
  (Board of Governors of the Federal Reserve System, H.10), retrieved from FRED, Federal Reserve Bank of St. Louis:
  `fred_EXKOUS_2020-01_2021-06.csv` (https://fred.stlouisfed.org/series/EXKOUS). Annual averages for reference:
  `fred_AEXKOUS_2020_2021.csv` (2020 = 1,180.56; 2021 = 1,144.89). Terms: https://fred.stlouisfed.org/legal/
  (cite FRED as the source).
- The dataset's "Item Price" is in KRW (dataset README: "Assessed value of an item (KRW)"); net mass in kg.
