# Third-party components and licences

All components are used under permissive licences. Versions are those installed for the demo build
(licences read from the installed package metadata).

## Datasets

| Dataset | Licence | Use |
|---|---|---|
| Customs Import Declaration Datasets — Institute for Basic Science & Korea Customs Service (https://github.com/Seondong/Customs-Declaration-Datasets, paper arXiv:2208.02484) | MIT | Training and test data (54,000 synthetic import declarations with fraud / critical-fraud outcomes). Downloaded to `data/raw/` (not redistributed in the repo). |
| datasets/harmonized-system (https://github.com/datasets/harmonized-system) | ODC-PDDL-1.0 (public domain) | HS6 / HS4 / HS2 product descriptions shown in the app and in the reasons. |

No Tunisian data is used. No administration website or information system is accessed.

## Python (backend and pipeline)

| Component | Version | Licence | Use |
|---|---|---|---|
| pandas | 3.0.6 | BSD-3-Clause | Data loading and preparation |
| NumPy | 2.5.3 | BSD-3-Clause (with 0BSD/MIT/Zlib parts) | Numerical computing |
| PyArrow | 25.0.1 | Apache-2.0 | Parquet artifacts |
| scikit-learn | 1.9.1 | BSD-3-Clause | K-fold, isotonic calibration, AUC |
| SciPy (scikit-learn dependency) | 1.18.1 | BSD-3-Clause | Numerical routines |
| LightGBM | 4.7.0 | MIT | The two risk models; TreeSHAP contributions (`pred_contrib`) |
| InterpretML / interpret-core (https://github.com/interpretml/interpret) | 0.7.8 | MIT | Explainable Boosting Machine (glass-box twin model, exact per-term contributions, shape functions) |
| joblib | 1.6.0 | BSD-3-Clause | Model persistence |
| FastAPI | 0.141.1 | MIT | HTTP API |
| Starlette | 1.7.0 | BSD-3-Clause | ASGI toolkit used by FastAPI; static files |
| Uvicorn | 0.54.0 | BSD-3-Clause | ASGI server |
| Pydantic | 2.13.5 | MIT | Request validation |
| python-dotenv | 1.2.3 | BSD-3-Clause | Optional `.env` settings |
| pytest | 9.1.1 | MIT | Tests |
| HTTPX | 0.28.1 | BSD-3-Clause | API test client |
| Playwright for Python | 1.63.0 | Apache-2.0 | Optional browser smoke test and screenshots (dev only) |

## JavaScript (web app v1, `frontend/`, kept as fallback)

| Component | Version | Licence | Use |
|---|---|---|---|
| React, React DOM | 19.3.0 | MIT | UI |
| React Router | 7.18.4 | MIT | Pages |
| Recharts | 3.10.1 | MIT | Charts |
| Framer Motion | 13.4.3 | MIT | Subtle animations |
| Lucide React | 1.48.0 | ISC | Icons |
| Sonner | 2.0.8 | MIT | Toasts |
| clsx | 2.1.1 | MIT | Class names |
| tailwind-merge | 3.7.0 | MIT | Class names |
| class-variance-authority | 0.7.1 | Apache-2.0 | Button variants |
| @fontsource/inter (Inter font) | 5.3.0 | OFL-1.1 | Self-hosted font |
| @fontsource/jetbrains-mono (JetBrains Mono font) | 5.3.0 | OFL-1.1 | Self-hosted font |
| @fontsource/noto-kufi-arabic (Noto Kufi Arabic font) | 5.3.0 | OFL-1.1 | Self-hosted font (logo "رقيب") |
| Vite | 8.3.1 | MIT | Build tool (dev) |
| @vitejs/plugin-react | 6.1.1 | MIT | Build tool (dev) |
| Tailwind CSS, @tailwindcss/vite | 4.3.3 | MIT | Styling (dev/build) |
| TypeScript | 5.9.3 | Apache-2.0 | Type checking (dev) |
| ESLint, @eslint/js | 10.11.0 / 10.0.1 | MIT | Linting (dev) |
| typescript-eslint | 8.70.1 | MIT | Linting (dev) |
| eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals | 7.1.1 / 0.5.7 / 17.12.0 | MIT | Linting (dev) |
| @types/react, @types/react-dom, @types/node | 19.3.0 / 19.3.0 / 26.6.2 | MIT | Type definitions (dev) |

UI components (cards, buttons, sliders, switches, tooltips) are our own Tailwind components in the style of
shadcn/ui; the shadcn CLI and Radix packages were not used.

## JavaScript (web app v2, `frontend-v2/`)

Built from the admin template **satnaing/shadcn-admin** (https://github.com/satnaing/shadcn-admin, MIT, © 2024 Sat Naing;
licence kept as `frontend-v2/LICENSE-shadcn-admin`). Reused: `src/components/ui` (shadcn/ui components), `src/components/data-table`,
the layout (sidebar, header), the command menu, theme / appearance settings and error pages. Removed: Clerk, auth pages and the demo apps.

| Component | Version | Licence | Use |
|---|---|---|---|
| satnaing/shadcn-admin (template) | 2.2.1 | MIT | App shell, UI components, data table, command menu |
| shadcn/ui components (via the template) | — | MIT | Buttons, cards, sheets, tabs, tables, tooltips... |
| Radix UI primitives (@radix-ui/react-*) | 1.1-2.3 | MIT | Accessible dialogs, sheets, menus, tabs, tooltips, switches |
| @radix-ui/react-icons | 1.3.2 | MIT | Data-table icons |
| TanStack Router / Query / Table | 1.170.39 / 5.103.2 / 8.21.3 | MIT | File routes, data fetching, worklist table |
| @tanstack/router-plugin, @tanstack/eslint-plugin-query | 1.168.40 / 5.103.2 | MIT | Route generation, linting (dev) |
| cmdk | 1.1.1 | MIT | Ctrl+K command palette |
| react-top-loading-bar | 3.0.2 | MIT | Navigation progress bar |
| tw-animate-css | 1.4.0 | MIT | CSS animations |
| React, React DOM | 19.3.0 | MIT | UI |
| Recharts | 3.10.1 | MIT | Charts |
| Framer Motion | 13.4.3 | MIT | Animations |
| Lucide React | 1.48.0 | ISC | Icons |
| Sonner | 2.0.8 | MIT | Toasts |
| clsx, tailwind-merge, class-variance-authority | 2.1.1 / 3.7.0 / 0.7.1 | MIT / MIT / Apache-2.0 | Class names |
| Tailwind CSS, @tailwindcss/vite | 4.3.3 | MIT | Styling |
| @fontsource/inter, jetbrains-mono, noto-kufi-arabic | 5.3.0 | OFL-1.1 | Self-hosted fonts |
| Vite, @vitejs/plugin-react | 8.3.1 / 6.1.1 | MIT | Build (dev) |
| TypeScript | 6.0.3 | Apache-2.0 | Type checking (dev) |
| ESLint, typescript-eslint, eslint-plugin-react-hooks/-refresh, globals | 10.11 / 8.70.1 / 7.1.1 / 0.5.7 / 17.12 | MIT | Linting (dev) |
| @types/node, @types/react, @types/react-dom | 25.9.8 / 19.3.0 / 19.3.0 | MIT | Type definitions (dev) |

## Tools and services

| Tool | Licence / terms | Use |
|---|---|---|
| Claude Code (Anthropic) | Commercial AI coding assistant | Used by the team to write and test the code. Not part of the product; no LLM is used for scoring or decisions. |
| Qwen3-4B (Alibaba Qwen team), `qwen3:4b-instruct-2507-q4_K_M` | Apache-2.0 | Optional local LLM: officer brief rephrasing and natural-language worklist filters. Never scores or decides. |
| Ollama (https://ollama.com) | MIT | Runs the local model on the laptop (HTTP on 127.0.0.1:11434). |
