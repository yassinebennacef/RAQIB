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
| 6b — Release-safe runtime | done | 00:28 | Build saves train_index.joblib + hs_names.json so the API runs without data/raw; `python -m raqib.check` lets run_demo skip or redo the build. Verified: full smoke test passes with data/raw hidden. |
| v2-A — Glass box, uncertainty, what-if, impact, model card, brief (branch v2) | done | 01:23 | EBM twin (cached, 230 s fit with n_jobs=4 after a memory crash with n_jobs=-1): fraud EBM AUC 0.771 / P@5 71.8% vs LightGBM 0.770 / 71.1% -> EBM primary for fraud; critical EBM R@5 67.1% vs 78.1% -> LightGBM stays primary. Disagreement threshold 0.179 (shadow models, last 4 training weeks): 371 flagged (4.4%), fraud rate 44.5%, never GREEN. Efficiency: same frauds with 19.4% fewer daily inspections (pooled 28.9%). Rejected: Isolation Forest AUC 0.477, 2-hop network 0.7690 vs 0.7696. New endpoints: worklist, whatif (~70 ms), efficiency, experiments, xai-global, model-card, brief (FR/EN/AR templates, no key). 22 tests pass. |
| v2-B — Professional UI (frontend-v2) | done | 01:45 | shadcn-admin (MIT) shell: sidebar, Ctrl+K palette (declarations, HS products, pages), dark/light, TanStack table worklist (server-side facets, sort, pages, side-sheet mini-inspector, bulk assign), control room race, inspector (exact waterfall, glass box vs black box, FR/EN/AR brief, decision), try + what-if, impact simulator, explainability (importances, shape functions, what-if, tested ideas), model lab, model card, decision journal (verify chain), about. Served by default (--ui v1 fallback). Playwright smoke tests v1 + v2 pass, also with data/raw hidden. |
| C — Integration | GO | 01:45 | build 23 s, 22 tests, lint+build v1 & v2, smoke v2 via run_demo.bat, smoke v2 without data/raw, smoke v1 fallback: all pass. v2 merged into main, tag v1.0-rc. |
| D — Local LLM (Qwen3-4B, Ollama) | GO | 02:49 | Officer brief FR/AR/EN (guarded, cached, template fallback) + Ask RAQIB (rules first, Qwen for free phrasing, validated filter, Apply). Model: qwen3:4b-instruct (the qwen3:4b tag is thinking-only: reasoning leaked, FR/AR unusable). Eval: brief guard 100%, fallback 0%, p50 6.9s, p95 9.9s; Ask RAQIB hybrid 100% exact, Qwen alone 73% exact / 98% fields. Go/no-go 7/7 (offline simulated: 0 external requests). |
| fix/qwen — Local LLM robustness | GO | — | Root causes (reproduced in tests): urllib sent 127.0.0.1:11434 through the system/env HTTP proxy (Ollama "unreachable"); model tag matched only if spelled exactly (`:latest`, `-2507-q8_0` ignored); Ollama probed once at start-up (started after RAQIB = template forever, no warm-up); background pre-generation of ~26 briefs held Ollama's slot so clicks timed out at 25 s; every fallback was silent. Fix: proxy-free local opener, tolerant model pick + `ollama pull` hint, re-probe every 10 s while down + auto warm-up, 120 s cold timeout, clicks before background jobs, `llm_fallback`/`llm_error` in /api/brief and /api/nlq, `last_error` in /api/llm/status, toast « LLM local indisponible → mode modèle », new sidebar page « Assistant (Qwen3 local) » (status, 3 example questions, example brief), run_demo.sh starts Ollama. 12 new tests (fake Ollama server); 44 tests pass; lint (4 pre-existing warnings) + build; smoke v2 offline with Ollama ON (stand-in server), OFF mid-demo (toast), RAQIB_LLM=off, never started, started after RAQIB. Models, metrics and replay untouched. |

## Tunisian edition (feat/tunisie, 2026-09-26)
- Currencies: dataset KRW -> USD at the data-period mean (FRED EXKOUS Jan 2020 - Jun 2021 = 1,158.87), -> TND / EUR at
  the 23/09/2026 reference rates (countryeconomy.com: 3.3701 TND/EUR, 2.9508 TND/USD; config/rates.json). API returns
  `{tnd, eur, usd}` for every amount + value_per_kg; TND | EUR | USD switch in the top bar (default TND), French format.
- Real public Tunisian data: UN Comtrade 2024 (reporter 788) saved in data/public_tn (SOURCES.md), built offline into
  artifacts/tunisia_ref.json (python -m raqib.tunisia): 1,170 HS6 reference unit values, top 15 chapters / origins,
  mirror gaps for the top 10 partners. Information only - never a model input. Page /tunisie, inspector card, worklist column.
- Measured check (honest): below 50% of the Tunisian reference = RED 99.3% vs GREEN 99.4% -> no separation; the synthetic
  dataset's values are ~0.6% of real prices at the median. Shown as such in the app.
- Impact: "Droits et taxes en jeu (estimation)", illustrative, TVA 19% as an assumption.
- Models, metrics, lanes and replay unchanged (317/259/103 frauds, 41/7/3 threats at 470 inspections).
- Also fixed a Windows timing flake in the LLM re-probe (RECHECK=0 compared with `>` on a 15 ms clock).

## Chat panel "Demander à Qwen" (feat/chat-panel, 2026-09-26)
- Floating, non-modal panel on every page: free questions to the local Qwen3 (FR / AR / EN), streamed (first token
  ~1 s once the model is loaded), Stop, clear, conversation kept across pages and reloads (sessionStorage).
- POST /api/chat: system prompt with RAQIB's measured facts worded as sentences (317/259/103 frauds, 41/7/3 threats,
  metrics, efficiency, uncertainty, UN Comtrade 2024) + the declaration's facts on /declaration/<id>; 503 with a clear
  message when Ollama is down. Hidden <think> blocks are filtered from the stream.
- The previous grounded assistant (branch fix/assistant) refused anything outside its knowledge base; it is left as is.
- Tests: tests/test_chat.py (fake streaming Ollama), tests/e2e/smoke_chat.py (real Qwen3, browser).
