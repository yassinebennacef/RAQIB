# RAQIB HTTP API (v0.9)

Base URL: `http://127.0.0.1:8000/api` · JSON everywhere · interactive docs at `/docs`.
Start with `python -m raqib.serve` (after `python -m raqib.build`).
Errors: `{"detail": "..."}` with 404 (unknown id / day), 422 (bad parameter), 503 (artifacts
missing - run the build). All probabilities are calibrated (0-1); "raw" scores are only used
for ranking. Truth labels are returned **for the demo only** (they are known after inspection).

Common query parameters:
- `rate` - daily inspection capacity as a share of the day's declarations (0.005-0.5, default 0.05)
- `explore` - share of the capacity drawn at random for exploration (0-0.5)

---

## GET /api/health
```json
{"status": "ok|degraded", "models_loaded": true, "artifacts": {"models/fraud_model.joblib": true, "...": true},
 "n_test_declarations": 8481, "n_days": 91, "error": null, "frontend_built": true}
```

## GET /api/data-card
Contents of `artifacts/data_card.json`:
```json
{"dataset": "...", "licence": "MIT", "source_url": "...", "hs_names": {"source_url": "...", "licence": "ODC-PDDL-1.0"},
 "rows": 54000, "columns": 22,
 "train": {"rows": 45519, "period": ["2020-01-01", "2021-03-31"], "days": 455, "fraud_rate": 0.216,
           "critical_rate": 0.0104, "n_fraud": 9818, "n_critical": 472},
 "test":  {"rows": 8481, "period": ["2021-04-01", "2021-06-30"], "days": 91, "...": "..."},
 "unique": {"importers": 0, "declarants": 0, "sellers": 0, "hs6": 0, "origins": 0, "offices": 0},
 "fraud_rate": 0.216, "critical_rate": 0.01,
 "hs_name_match": {"hs6": 0.96, "hs4_fallback": 0.03, "none": 0.01},
 "test_new_operators": {"importer": 0.0, "declarant": 0.0, "seller": 0.0, "hs6": 0.0},
 "notes": ["..."]}
```
(Numbers above are placeholders for the shape; the real values come from the file.)

## GET /api/metrics
Contents of `artifacts/metrics.json`:
```json
{"generated_at": "ISO time",
 "recipe": {"train": [..], "test": [..], "n_train": 45519, "n_test": 8481, "features": [..],
            "lgbm_params": {..}, "smoothing_a": {"fraud": 10, "critical": 20}, "topk": "..."},
 "method_labels": {"ai": "RAQIB AI", "rule_hs6_history": "...", "rule_importer_history": "...", "random": "..."},
 "targets": {
   "fraud|critical": {
     "label": "Duty fraud (revenue)", "base_rate": 0.216, "n_positive": 1835, "prior_train": 0.216,
     "methods": {"ai|rule_hs6_history|rule_importer_history|random": {
        "auc": 0.77,
        "precision_at_1": 0, "precision_at_5": 0, "precision_at_10": 0,
        "recall_at_1": 0, "recall_at_5": 0, "recall_at_10": 0,
        "caught_at_5": 0, "k_at_5": 425, "precision_se_at_5": 0, "recall_se_at_5": 0, "...": "same for 1 and 10"}},
     "calibration": [{"bin": 1, "n": 849, "mean_predicted": 0.01, "observed": 0.02}],
     "weekly": [{"week": 1, "start": "2021-04-01", "n": 600, "positives": 120, "base_rate": 0.2,
                 "precision_ai": 0.7, "recall_ai": 0.16, "precision_rule": 0.5, "recall_rule": 0.12}],
     "importance": {"features": [{"feature": "rate_hs6", "share": 0.4}],
                    "groups": [{"group": "product", "label": "Product (HS6) history", "share": 0.5}]},
     "gain_vs_rule": {"metric": "precision_at_5", "mean_gain": 0.17, "ci95": [0.12, 0.21], "n_boot": 500,
                      "share_boot_ai_better": 1.0}}},
 "fairness": {"k": 425, "share": 0.05,
   "office|transport": {"rows": [{"code": "40", "label": "...", "n": 2950, "share_declarations": 0.35,
       "share_inspections_ai": 0.3, "share_inspections_rule": 0.3, "selection_rate_ai": 0.05,
       "selection_rate_rule": 0.05, "fraud_rate": 0.2}], "max_min_selection_ratio_ai": 3.1}},
 "n_critical_test": 73,
 "thresholds": {"alert_threshold": 0.13, "red_threshold": 0.52, "yellow_threshold": 0.34,
                "alert_p_critical": 0.13, "red_p_fraud": 0.58, "yellow_p_fraud": 0.38, "note": "..."},
 "replay_summary": {"rate": 0.05, "explore": 0.1, "n_days": 91,
   "totals": {"declarations": 8481, "frauds": 1835, "threats": 73, "inspections": 470},
   "policies": {"ai|ai_explore|rule|random": {"label": "...", "inspections": 470, "frauds": 0, "threats": 0,
       "hit_rate": 0, "fraud_recall": 0, "threat_recall": 0, "distinct_hs6": 0, "explored": 0,
       "explored_frauds": 0, "green_share": 0.85, "yellow_share": 0.1}}}}
```

## GET /api/replay?rate=0.05&explore=0.1
Day-by-day replay of the test period, computed live (cached per parameters, < 100 ms).
`ai` never explores; `ai_explore` uses `explore`. Capacity per day is identical for all policies.
```json
{"rate": 0.05, "explore": 0.1, "seed": 7, "n_days": 91,
 "dates": ["2021-04-01", "..."], "n": [93, "..."], "capacity": [5, "..."],
 "day_frauds": [20, "... frauds among all declarations of the day"], "day_threats": [1, "..."], "alert_threshold": 0.135,
 "totals": {"declarations": 8481, "frauds": 1835, "threats": 73, "inspections": 470},
 "policies": {
   "ai|ai_explore|rule|random": {
     "label": "RAQIB AI",
     "frauds": [3, "... per day"], "threats": [0], "cum_frauds": [3], "cum_threats": [0],
     "cum_inspected": [5], "distinct_hs6": [5], "explored": [0], "explored_frauds": [0],
     "red": [5], "yellow": [10], "green": [78], "alerts": [1],
     "summary": {"inspections": 470, "frauds": 309, "threats": 40, "hit_rate": 0.66, "fraud_recall": 0.17,
                 "threat_recall": 0.55, "distinct_hs6": 262, "explored": 0, "explored_frauds": 0,
                 "green_share": 0.84, "yellow_share": 0.1}}}}
```
`red`, `yellow`, `green`, `alerts`, `green_share`, `yellow_share` exist for `ai` and `ai_explore` only.

## GET /api/stream?day=N&rate=0.05&explore=0
The declarations of day N (0-90) with their lanes at this capacity.
```json
{"day": 4, "date": "2021-04-05", "n": 300, "capacity": 15, "rate": 0.05, "explore": 0.0,
 "items": [{"id": "23218937", "hs6": "392690", "hs_desc": "Plastics; other articles ...", "origin": "CN",
            "office_label": "...", "transport_label": "Air", "item_price": 1200.5, "net_mass": 3.0,
            "lane": "RED|YELLOW|GREEN", "alert": false, "explored": false, "rule_selected": true,
            "p_fraud": 0.71, "p_critical": 0.004, "rank_in_day": 1, "top_reason": "Product ...",
            "truth": {"fraud": 1, "critical": 0}}],
 "truth_note": "Truth labels are shown for the demo only (known after inspection)."}
```

## GET /api/declaration/{id}?rate=0.05&explore=0
```json
{"declaration": {"id": "...", "date": "...", "hs6": "030214", "hs_desc": "...", "office": 20, "office_label": "...",
                 "transport": 10, "transport_label": "Maritime", "origin": "NO", "departure": "NO",
                 "importer": "...", "declarant": "...", "seller": "...", "courier": null,
                 "process_type": "B", "import_type": 11, "import_use": 21, "payment_type": 11,
                 "tax_type": "A", "origin_indicator": "G", "tax_rate": 0, "net_mass": 0, "item_price": 0,
                 "unit_value": 0},
 "ai": {"p_fraud": 0.62, "p_critical": 0.01, "fraud_percentile": 97.5, "critical_percentile": 60.1,
        "lane": "RED", "alert": false, "explored": false, "lane_reason": "...", "rank_in_day": 3,
        "reasons_fraud": [{"group": "product", "label": "Product (HS6) history", "text": "...",
                           "contribution": 1.61, "direction": "raises|lowers", "thin_history": true}],
        "reasons_critical": ["2 items, same shape"]},
 "rule": {"name": "Product (HS6) history", "score": 0.39, "hs6_past_declarations": 11,
          "hs6_past_fraud_rate": 0.55, "rank_in_day": 30, "selected": false,
          "decision": "INSPECT|RELEASE", "explanation": "..."},
 "day": {"index": 4, "date": "...", "n": 300, "capacity": 15, "rate": 0.05},
 "truth": {"fraud": 1, "critical": 0, "critical_code": 1, "note": "..."},
 "history": {"importer|declarant|seller": {"id": "...", "role": "importer", "past_declarations": 4,
                                           "is_new": false, "fraud_rate": 0.25, "critical_rate": 0,
                                           "thin_history": true},
             "average_fraud_rate": 0.216},
 "network": {"nodes": [{"id": "importer:XYZ", "type": "importer|declarant|seller", "label": "XYZ",
                        "is_focus": true, "past_declarations": 4, "fraud_rate": 0.25}],
             "links": [{"source": "declarant:ABC", "target": "importer:XYZ", "past_declarations": 12}],
             "note": "..."},
 "decisions": ["previous decisions on this declaration (same shape as /api/decisions entries)"]}
```
Contributions are exact TreeSHAP values (log-odds) summed by concept.

## POST /api/score
Request (empty operator id = new operator):
```json
{"hs6": "621149", "origin": "CN", "office": 40, "importer_id": "", "declarant_id": "", "seller_id": "",
 "tax_rate": 13, "net_mass": 45, "item_price": 12300, "transport": 40}
```
Response:
```json
{"input": {"hs6": "621149", "hs_description": "...", "origin": "CN", "office": 40, "office_label": "...",
           "transport": 40, "transport_label": "Air", "importer_id": "", "declarant_id": "", "seller_id": "",
           "tax_rate": 13, "net_mass": 45, "item_price": 12300},
 "p_fraud": 0.51, "p_critical": 0.01, "fraud_percentile": 88.0, "critical_percentile": 70.2,
 "alert": false, "lane": "RED|YELLOW|GREEN", "lane_reason": "...",
 "reasons_fraud": ["4 reasons"], "reasons_critical": ["2 reasons"],
 "notes": ["New importer: no history (treated as average risk)."],
 "thresholds": {"red_p_fraud": 0.58, "yellow_p_fraud": 0.38, "alert_p_critical": 0.13},
 "transport_used_by_model": false}
```

## GET /api/presets
Three real test declarations for the form: `high_fraud`, `safety_alert`, `low_risk`.
```json
[{"key": "high_fraud", "label": "...", "description": "...", "source_declaration_id": "...",
  "declaration": {"...": "same fields as POST /api/score"}, "hs_desc": "..."}]
```

## GET /api/hs/search?q=coffee
Up to 20 HS6 codes whose description contains the text (or whose code starts with it),
most frequent in the training period first.
```json
[{"hs6": "090111", "description": "Coffee; not roasted or decaffeinated", "past_declarations": 28}]
```

## POST /api/decision
```json
{"declaration_id": "32548159", "decision": "INSPECT|DOCUMENT_CHECK|RELEASE", "comment": "...", "officer": "Officer A"}
```
Response: `{"id": 1, "hash": "sha256 hex", "prev_hash": "sha256 hex", "ts": "ISO time"}`.
The record (with the AI lane and probabilities at decision time) is appended to
`artifacts/decisions.jsonl`; `hash = sha256(prev_hash + canonical JSON of the record)`.

## GET /api/decisions?limit=200
```json
{"entries": [{"id": 2, "ts": "...", "declaration_id": "...", "decision": "RELEASE", "comment": "",
              "officer": "Officer B", "ai": {"lane": "GREEN", "p_fraud": 0.1, "p_critical": 0.0},
              "prev_hash": "...", "hash": "..."}],
 "verify": {"ok": true, "n_entries": 2, "first_bad_id": null}}
```
Newest first. `verify` recomputes the whole chain: any edited, deleted or reordered line is detected.


---

# v2 additions (branch v2) — contract first

All v2 fields are **additive**: every v1 field above keeps its name and meaning.
`model` values: `"lightgbm"` | `"ebm"` (Explainable Boosting Machine, glass box). `primary` = the model that
drives lanes, replay and "ai" metrics for that target (chosen by the rule in the model card).

## Waterfall object (used below)
Exact additive explanation of one model's probability for one declaration: start from the model's base value,
add each concept group's contribution (log-odds), convert the running sum to a probability after each step.
```json
{"model": "ebm", "target": "fraud",
 "base": 0.183,
 "final": 0.642,
 "steps": [{"group": "product", "label": "Product (HS6) history", "contribution": 1.21,
            "delta": 0.211, "cumulative": 0.394}],
 "other": {"contribution": 0.05, "delta": 0.01},
 "note": "..."}
```
- `base` = sigmoid(intercept or bias); `final` = the model probability = sigmoid(base log-odds + all contributions).
- `contribution` is in log-odds; `delta` and `cumulative` are in probability terms. Top 6 groups by |contribution|,
  the rest summed in `other`.
- Groups: product, family, chapter, importer, declarant, seller, origin, office, tax, value, interaction (EBM pairs).

## GET /api/declaration/{id} — new fields
```json
{"ai": {"uncertain": false, "disagreement": 0.031,
        "models": {"primary": {"fraud": "ebm", "critical": "lightgbm"},
                   "lightgbm": {"p_fraud": 0.61, "p_critical": 0.012},
                   "ebm": {"p_fraud": 0.64, "p_critical": 0.010}}},
 "waterfall": {"...": "Waterfall of the primary fraud model"},
 "waterfall_critical": {"...": "Waterfall of the primary critical model"}}
```
`uncertain` = the two fraud models disagree by more than the 95th percentile of their disagreement measured
out-of-sample on the last 4 training weeks; such a declaration is never released GREEN (it goes to YELLOW).

## GET /api/stream — new item fields
`"uncertain": bool, "disagreement": float` on every item.

## GET /api/worklist
Query (all optional): `day` (0-90, default all), `lane=RED,YELLOW`, `origin=CN,KR`, `hs2=61,85`, `office=30`,
`uncertain=true`, `min_p=0.3`, `q=text` (id, HS code, product name, importer, declarant, seller),
`sort` (p_fraud | p_critical | date | disagreement | item_price), `order` (asc | desc), `page`, `page_size`,
`rate`, `explore`.
```json
{"total": 470, "page": 1, "page_size": 50,
 "facets": {"lane": {"RED": 470, "YELLOW": 900, "GREEN": 7111}, "uncertain": {"true": 400, "false": 8081},
            "origin": [{"value": "CN", "n": 2500}],
            "office": [{"value": "30", "label": "Busan Regional Customs", "n": 1400}],
            "hs2": [{"value": "85", "label": "Electrical machinery ...", "n": 900}]},
 "items": [{"id": "83368645", "date": "2021-06-30", "day": 90, "hs6": "853590", "hs_desc": "...", "hs2": "85",
            "origin": "CN", "office": 30, "office_label": "...", "transport_label": "Air", "item_price": 1200.0,
            "lane": "RED", "alert": false, "uncertain": false, "disagreement": 0.02,
            "p_fraud": 0.66, "p_critical": 0.004, "top_reason": "...", "rule_decision": "RELEASE",
            "truth": {"fraud": 1, "critical": 0}}]}
```

## POST /api/whatif
Request: a test declaration id or a form declaration (same fields as POST /api/score), plus changes
(all optional; operator values are an id or `"new"`):
```json
{"declaration_id": "83368645",
 "declaration": null,
 "changes": {"item_price": 5000, "net_mass": 10, "tax_rate": 8, "origin": "CN", "hs6": "621149",
             "importer": "new", "declarant": "ABC1234", "seller": "new"}}
```
Response (< 300 ms):
```json
{"before": {"p_fraud": 0.64, "p_critical": 0.01, "lane": "RED", "alert": false,
            "waterfall": {"...": "Waterfall"}, "reasons_fraud": ["4 reasons"]},
 "after":  {"...": "same shape"},
 "deltas": [{"group": "value", "label": "Value and mass", "before": 0.10, "after": -0.35, "delta": -0.45}],
 "changed": ["item_price", "importer"],
 "note": "Officer-only simulation tool; never shown to traders."}
```

## GET /api/efficiency?minutes_per_inspection=60
Daily replay (same rules as /api/replay, no exploration) for capacities 1% to 20%, plus the "same result with
fewer inspections" comparisons.
```json
{"curve": [{"rate": 0.01, "inspections": 105, "ai": {"frauds": 90, "threats": 20},
            "rule": {"frauds": 60, "threats": 3}, "random": {"frauds": 22, "threats": 1}}],
 "matching": {"reference": {"policy": "rule", "rate": 0.05, "inspections": 470, "frauds": 259},
              "ai_rate": 0.04, "ai_inspections": 381, "ai_frauds": 261,
              "fewer_inspections": 89, "fewer_pct": 0.19},
 "pooled": {"k_rule": 425, "rule_frauds": 227, "k_ai_needed": 300, "fewer_inspections": 125, "fewer_pct": 0.29},
 "threats": {"rule_at_5": 7, "ai_rate_matching_threats": 0.01, "ai_inspections": 105},
 "officer_hours": {"minutes_per_inspection": 60, "assumption": true,
                   "hours_freed_test_period": 89.0, "test_days": 91, "hours_freed_per_year": 357.0}}
```

## GET /api/experiments
```json
{"experiments": [
  {"key": "ebm", "title": "Glass-box model (EBM)", "decision": "kept", "hypothesis": "...", "method": "...",
   "result": {"fraud_auc": 0.77, "fraud_precision_at_5": 0.717, "critical_auc": 0.95, "critical_recall_at_5": 0.76},
   "baseline": {"...": "same keys for LightGBM"}, "reason": "..."},
  {"key": "disagreement", "title": "Uncertainty from model disagreement", "decision": "kept", "result": {}},
  {"key": "isolation_forest", "title": "Anomaly detection (Isolation Forest)", "decision": "rejected",
   "result": {"fraud_auc": 0.48, "top1_fraud_rate": 0.21, "base_rate": 0.216}, "reason": "no signal"},
  {"key": "network_2hop", "title": "2-hop network features", "decision": "rejected",
   "result": {"auc_with": 0.7687, "auc_without": 0.7702, "p5_with": 0.70, "p5_without": 0.71},
   "reason": "CTGAN synthesises rows independently, so cross-row links are artefacts; re-test on real Tunisian data."}]}
```
(Numbers above only show the shape; real values come from artifacts/experiments.json.)

## GET /api/xai-global
```json
{"primary_model": {"fraud": "ebm", "critical": "lightgbm"},
 "targets": {"fraud": {
   "model": "ebm", "intercept": -1.6, "base_rate": 0.216,
   "importances": [{"term": "rate_hs6", "label": "Past fraud rate of the product (HS6)", "group": "product",
                    "importance": 0.41, "share": 0.35}],
   "shapes": [{"term": "rate_hs6", "label": "Past fraud rate of the product (HS6)",
               "x_label": "past fraud rate of the product (%)", "y_label": "effect on risk (log-odds)",
               "points": [{"x": 5.0, "y": -0.8, "lower": -0.9, "upper": -0.7}]}]},
  "critical": {"...": "same shape"}}}
```
The top 8 main-effect terms get a shape (x in natural units: rates in %, counts, tax %, mass kg, value KRW).

## GET /api/model-card
```json
{"title": "RAQIB model card", "version": "v2", "generated_at": "...",
 "sections": [{"key": "intended_use", "title": "Intended use", "text": "...", "bullets": ["..."],
               "table": {"columns": ["Metric", "Value"], "rows": [["AUC", "0.770"]]}}]}
```
Sections: intended_use, users, out_of_scope, data, models, metrics, calibration, fairness, uncertainty,
tested_and_rejected, limits, human_oversight, monitoring, contact. Same content in docs/MODEL_CARD.md.

## POST /api/brief/{id}?lang=fr|en|ar
```json
{"id": "83368645", "lang": "fr", "text": "4 sentences for the officer ...", "source": "template",
 "model": null, "cached": false, "facts": {"p_fraud": 0.64, "lane": "RED"}}
```
Without an OpenAI key the brief is a deterministic template built only from the computed facts (FR / EN / AR).

## GET /api/metrics — new keys
```json
{"primary_model": {"fraud": "ebm", "critical": "lightgbm", "rule": "..."},
 "targets": {"fraud": {"methods": {"ai": {"...": "primary model"}, "lightgbm": {}, "ebm": {}}}},
 "uncertainty": {"threshold": 0.12, "n_flagged": 424, "share_flagged": 0.05, "fraud_rate_flagged": 0.35,
                 "fraud_rate_all": 0.216, "green_to_yellow": 120, "fraud_rate_green_to_yellow": 0.18},
 "efficiency": {"...": "matching + pooled, as in /api/efficiency"}}
```


---

# Local LLM additions (optional, Qwen3-4B via Ollama)

The LLM never scores, ranks, chooses a lane or decides. With `RAQIB_LLM=off` (or Ollama not reachable) every
endpoint below still answers, using the deterministic template / rule-based parser.

## POST /api/brief
Request `{"id": "54794554", "lang": "fr|ar|en", "refresh": false}` →
```json
{"text": "4 sentences ...\nContrôle suggéré: ...", "lang": "fr", "dir": "ltr|rtl", "source": "qwen3-4b|template",
 "model": "qwen3:4b-instruct-2507-q4_K_M", "guard_passed": true, "latency_ms": 6900, "cached": false,
 "facts_used": {"declaration_id": "...", "lane": "...", "fraud_risk_percent": 70.2, "risk_indicators": ["..."]}}
```
Guards: every number must be in the facts (rounding, percent/fraction and Arabic-Indic digits handled), banned
accusatory claims, right language, no echo of the instructions; one retry at temperature 0, then the template.
Cached in `artifacts/brief_cache/{id}_{lang}.json`. (The older `POST /api/brief/{id}?lang=` template endpoint is kept.)

## POST /api/nlq
Request `{"q": "déclarations rouges d'origine CN au chapitre 85 au-dessus de 80%"}` →
```json
{"filter": {"lane": ["RED"], "min_fraud": 0.8, "safety_only": false, "uncertain_only": false, "origin": ["CN"],
            "hs_prefix": ["85"], "office": null, "importer": null, "date_from": null, "date_to": null,
            "sort": "fraud_desc", "limit": 50},
 "source": "rules|qwen3-4b", "warnings": [], "explanation": "lane RED · fraud risk ≥ 80% · origin CN · HS 85 · ..."}
```
Rules first (when the rule parser recognises the question), otherwise Qwen with a JSON schema; always validated
against the real data vocabularies. `explanation` is generated from the filter, not by the LLM.

## POST /api/worklist/query
Request `{"filter": {...NLQ filter...}, "page": 1, "page_size": 50}` → same shape as `GET /api/worklist`.
`GET /api/worklist` also accepts `hs_prefix`, `importer`, `date_from`, `date_to`, `alert` (safety alerts only).

## GET /api/llm/status
`{"enabled": true, "mode": "ollama|off", "model": "...", "reachable": true, "warm": true, "avg_latency_ms": 6665,
  "calls": 7, "errors": 0, "installed_models": ["..."]}`

## GET /api/llm/eval
Contents of `artifacts/llm_eval.json` (written by `scripts/eval_llm.py`), or `{"skipped": true}`.
