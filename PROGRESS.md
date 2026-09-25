# RAQIB — progress log

| Phase | Status | Time | Notes |
|---|---|---|---|
| 0 — Repo setup | done | 23:45 | Clean repo (was empty). Python 3.12 venv (3.11 not installed on the demo laptop). pnpm via `corepack pnpm` (corepack enable needs admin). |
| 1 — Data | done | 23:54 | Both public datasets cloned to data/raw (gitignored). TRAIN 45,519 / TEST 8,481 rows; 73 critical cases in TEST. data_card.json. |
| 2 — Models + measured results | done | 23:54 | Recipe reproduced: fraud AUC 0.770, P@5% 0.704 vs rule 0.534; critical AUC 0.949, R@5% 0.767 vs rule 0.548. |
| 3 — Explanations, replay, scoring | done | 23:54 | TreeSHAP reasons (4 per model), replay at 5%: AI 309 frauds / 40 threats vs rule 259 / 7 vs random 103 / 3. Build 15 s. 7 tests pass. |
| 4 — API | done | 23:57 | FastAPI: health, data-card, metrics, replay (live, cached), stream, declaration (reasons, rule, history, network), score, presets, HS search, hash-chained decisions. API.md. Warm calls 2-25 ms. 14 tests pass. |
| 5 — Web app | done | 00:15 | Vite 8 + React 19 + TS + Tailwind 4 control room: Control room (race replay, live feed, KPIs), Inspector (gauges, TreeSHAP reasons, rule side-by-side, operator history + network, decision journal), Try a declaration (HS search, presets), Model lab, About. shadcn CLI skipped (very slow npm registry here) -> equivalent Tailwind components. Blank seller IDs now treated as missing (numbers even closer to the reference: P@5% 0.711, replay 315/40). Playwright smoke test (Edge): no console errors. |
| 6 — Docs, tests, one-command demo | done | 00:25 | run_demo.bat / run_demo.sh (tested), README + THIRD_PARTY.md, docs generated from artifacts by `python -m raqib.report` (NOTE_DRAFT, DECK_OUTLINE, DEMO_SCRIPT, RESULTS), value/mass ablation (value DOES carry signal here: P@5% 0.711 -> 0.633 without it), Playwright smoke test + 9 screenshots, tag v0.9-demo. |
