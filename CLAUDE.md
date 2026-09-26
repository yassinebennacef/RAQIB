# RAQIB — working rules (read fully before any task)

RAQIB (Arabic "رقيب", overseer) is the prototype of team RAQIB for the Tunisian national
hackathon "IA & Finances Publiques" (École Nationale des Douanes + École Nationale des
Finances), challenge **T2 « Ciblage et orientation automatisés des contrôles »**.

## What RAQIB does
RAQIB decides which import declarations customs should physically inspect under a fixed
daily inspection capacity. Every day it:
- scores every declaration with two AI models: **duty fraud** (revenue) and **critical
  fraud** (public-safety threat);
- fills the capacity: public-safety alerts first, then the highest fraud probabilities,
  plus an optional small random share ("exploration") so the system never goes blind;
- gives each declaration a lane (RED = inspect, YELLOW = document check, GREEN = release)
  with 4 plain-English reasons;
- shows, side by side, what today's best rule (product history) would have chosen, so the
  measured gain is visible;
- leaves the decision to the human officer and logs it in a hash-chained journal.

## Hard rules
- Data: ONLY the public datasets in data/raw (Customs Import Declaration Datasets, MIT,
  IBS + Korea Customs Service; datasets/harmonized-system, ODC-PDDL). No Tunisian data, no
  scraping, no contact with any government or administration website or system.
- Never invent or hard-code a result. Every number shown in the app or in the docs is
  computed by the code from the data (artifacts/metrics.json, replay_default.json...).
- Every third-party library and dataset is listed with its licence in THIRD_PARTY.md
  (permissive licences only).
- Never commit or print secrets (.env).

## Layout
- backend/raqib/ — Python package (pip install -e .)
  - config.py (paths, recipe constants), data.py (loaders, HS names, data card)
  - model.py (out-of-fold target encoding + LightGBM + isotonic calibration)
  - baselines.py (random, importer history, HS6 history rules), evaluate.py (metrics.json)
  - explain.py (TreeSHAP contributions -> 4 grouped plain-English reasons)
  - replay.py (day-by-day capacity replay), score.py (score a new declaration)
  - decisions.py (hash-chained decision log), build.py (`python -m raqib.build`)
  - api.py (FastAPI, see API.md), serve.py (`python -m raqib.serve`)
- frontend-v2/ — v2 web app (default): shadcn-admin (MIT) shell, TanStack Router/Query/Table; pages in src/features.
- frontend/ — v1 control-room UI, kept as the fallback (`python -m raqib.serve --ui v1`).
- artifacts/ — build outputs (gitignored until release): models/, metrics.json,
  data_card.json, replay_default.json, test_scored.parquet, decisions.jsonl.
- data/raw/ — downloaded datasets (gitignored; `python -m raqib.data --download`).
- docs/ — note de synthèse draft, deck outline, demo script, screenshots.

## Commands (Windows, Git Bash; never rely on venv activation)
- Build data + models + metrics (+ regenerates README numbers and docs/*.md): `.venv/Scripts/python -m raqib.build`
- Regenerate only the docs from artifacts: `.venv/Scripts/python -m raqib.report`
- Serve API + built UI: `.venv/Scripts/python -m raqib.serve --port 8000`
- Tests: `.venv/Scripts/python -m pytest -q`
- Front end dev: `cd frontend && corepack pnpm dev` (proxy /api -> 127.0.0.1:8000)
- Front end build: `cd frontend && corepack pnpm build`
- One-command demo: `run_demo.bat` (Windows) or `./run_demo.sh`

## Model recipe (do not change without re-measuring)
Targets: fraud = Fraud (a=10); critical = (Critical Fraud == 2) (a=20).
TRAIN = train + valid CSV (2020-01-01..2021-03-31), TEST = test CSV (2021-04..2021-06).
Keys: HS6, hs4, hs2, importer, declarant, seller, origin, office ->
rate = (sum + a*prior)/(count + a), count; out-of-fold on TRAIN (KFold 5, seed 0);
TEST uses full-TRAIN statistics. Numerics: tax rate, net mass, item price,
unit = log1p(price / max(mass, 0.1)). LightGBM (300 trees, lr 0.03, 15 leaves,
min_child_samples 100, subsample 0.8, colsample 0.8, seed 42). Isotonic calibration on
out-of-fold TRAIN predictions (KFold 5, seed 1). Ranking uses the raw model score
(identical order to the calibrated probability, without ties).

## Engineering
- Python 3.12 venv at .venv (3.11 also fine). pathlib everywhere. No Docker.
- Front end: dark control-room design (slate-950 background, slate-900 cards).
  Colours: AI #2a78d6, RULE #eb6834, RANDOM #9a9893, RED lane #EF4444,
  YELLOW #F59E0B, GREEN #22C55E. Self-hosted fonts (@fontsource Inter, JetBrains Mono):
  the demo must work offline. Every number on screen comes from the API.
- Footer on every page: "Real customs declarations (public MIT dataset, Korea Customs
  Service / IBS) · no Tunisian data used · advisory: the officer decides".
- Working first, then polish. Tests must pass before every commit.
- End of every phase: run tests, append to PROGRESS.md, commit "Phase N: ...", push.

## Release (when the user types "RELEASE")
1. `.venv/Scripts/python -m raqib.build` (fresh artifacts + regenerated docs), tests, `pnpm lint && pnpm build`.
2. Force-add the runtime artifacts (the app then runs from a fresh clone without data/raw):
   `git add -f artifacts/models artifacts/metrics.json artifacts/data_card.json artifacts/replay_default.json
    artifacts/test_scored.parquet artifacts/train_index.joblib artifacts/hs_names.json artifacts/efficiency.json
    artifacts/experiments.json artifacts/xai_global.json artifacts/model_card.json frontend/dist frontend-v2/dist`
   (never decisions.jsonl, logs or screenshots scratch; check the total is < 100 MB).
3. `git commit -m "Release v1.0"`, `git tag -a v1.0 -m "RAQIB v1.0"`, `git push --follow-tags`.
