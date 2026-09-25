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
