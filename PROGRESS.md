# RAQIB — progress log

| Phase | Status | Time | Notes |
|---|---|---|---|
| 0 — Repo setup | done | 23:45 | Clean repo (was empty). Python 3.12 venv (3.11 not installed on the demo laptop). pnpm via `corepack pnpm` (corepack enable needs admin). |
| 1 — Data | done | 23:54 | Both public datasets cloned to data/raw (gitignored). TRAIN 45,519 / TEST 8,481 rows; 73 critical cases in TEST. data_card.json. |
| 2 — Models + measured results | done | 23:54 | Recipe reproduced: fraud AUC 0.770, P@5% 0.704 vs rule 0.534; critical AUC 0.949, R@5% 0.767 vs rule 0.548. |
| 3 — Explanations, replay, scoring | done | 23:54 | TreeSHAP reasons (4 per model), replay at 5%: AI 309 frauds / 40 threats vs rule 259 / 7 vs random 103 / 3. Build 15 s. 7 tests pass. |
