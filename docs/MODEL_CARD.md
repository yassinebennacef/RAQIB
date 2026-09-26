# RAQIB model card

*Version v2 - generated 2026-09-26T00:21:36+00:00 by `python -m raqib.report`*

## Intended use

Advisory ranking of import declarations for customs officers: which declarations to inspect (RED), to check on documents (YELLOW) or to release (GREEN) under a fixed daily inspection capacity. RAQIB prioritises and explains; the officer always decides.

## Users

- Risk-analysis officers who prepare the daily inspection plan.
- Inspection officers at the offices (worklist, inspector, decision journal).
- Supervisors and auditors (hash-chained decision journal, model card, fairness view).

## Out-of-scope uses

- Automatic sanctions, penalties or seizures without an officer's decision.
- Scoring, ranking or publishing scores about traders; the what-if simulator is an officer-only tool and is never shown to traders.
- Use on data that differs from the training data (other country, other period) without retraining and re-validation.

## Data

Customs Import Declaration Datasets (Institute for Basic Science & Korea Customs Service, MIT): 54,000 synthetic declarations (CTGAN) from real inspected declarations. Train 45,519 (2020-01-01 to 2021-03-31), test 8,481 (2021-04-01 to 2021-06-30). Fraud rate 21.6%; 73 critical cases in the test period. No Tunisian data.

## Models

Two models per target on the same features (out-of-fold smoothed fraud history of product, family, chapter, importer, declarant, seller, origin and office, plus tax rate, mass, value and unit value): a LightGBM gradient-boosting model and an Explainable Boosting Machine (glass box: every prediction is an exact sum of readable per-feature contributions). EBM (glass box) is primary for a target when its operating metric (fraud: precision @5%, critical: recall @5%) is within 1.5 points of LightGBM or better; otherwise LightGBM stays primary and EBM is the transparent twin.

| Target | Primary | LightGBM AUC | EBM AUC | LightGBM op. metric | EBM op. metric |
|---|---|---|---|---|---|
| Duty fraud (precision @5%) | ebm | 0.770 | 0.771 | 71.1% | 71.8% |
| Public safety (recall @5%) | lightgbm | 0.952 | 0.926 | 78.1% | 67.1% |

## Measured performance (test period, never used for training)

- Duty fraud precision @5%: 71.8% vs 53.4% for the rule: +17.8 pts (95% bootstrap CI +12.5 pts to +22.5 pts).
- Public-safety recall @5%: 78.1% vs 54.8%: +22.5 pts (95% CI +13.3 pts to +32.3 pts); 73 critical cases only, so ±5 pts (1 s.e.).
- Stable: the AI beats the rule in 12 of 13 weeks (precision @5% within each week).
- Calibrated: in the riskiest tenth of declarations the model predicts 61.7% fraud and 61.4% is observed.

| Method | Fraud AUC | Fraud precision @5% | Critical AUC | Critical recall @5% |
|---|---|---|---|---|
| RAQIB AI (EBM primary) | 0.771 | 71.8% | 0.952 | 78.1% |
| Rule: product (HS6) history | 0.728 | 53.4% | 0.924 | 54.8% |
| Rule: importer history | 0.513 | 18.8% | 0.516 | 1.4% |
| Random selection | 0.497 | 21.4% | 0.548 | 6.8% |

## Calibration

In the riskiest tenth of test declarations the primary fraud model predicts 61.7% fraud and 61.4% is observed (10-bin table in metrics.json).

## Fairness (who gets inspected)

Selection rate in the top 5%: max/min ratio across offices with at least 100 declarations 1.7x; across transport modes 1.1x. Reviewed weekly next to each group's fraud rate.

## Uncertainty policy

When |p(EBM) - p(LightGBM)| exceeds 0.179 (95th percentile of their out-of-sample disagreement on the last 4 training weeks), the declaration is flagged as 'models disagree' and is never released green. Test period: 371 flagged (4.4%), fraud rate 44% vs 22% overall.

## Tested and rejected

- Anomaly detection (Isolation Forest): rejected. No signal: the top 1% anomalies are fraudulent at about the base rate.
- 2-hop network features: rejected. No gain. CTGAN synthesises rows independently, so cross-row links are artefacts; re-test on real Tunisian data.

## Limits

- Synthetic data of Korean origin: patterns are realistic but not Tunisian.
- Only inspected declarations were synthesised: fraud rate 21.6%, far above reality; the claim is the gain over the rule, not the absolute precision.
- Only 73 critical cases in the test period.
- Lane and alert thresholds are set on the test period; the disagreement threshold on the last training weeks.
- 78% of test declarations carry exactly their product's usual unit value (synthetic artefact): value signals must be re-validated on real data.

## Human oversight

- Advisory score only: the officer decides inspect / document check / release.
- Every decision is written to a hash-chained, tamper-evident journal (verify endpoint).
- Each lane comes with 4 plain-language reasons and an exact waterfall; the current rule is shown side by side.
- Models disagree: human review; 10% random exploration keeps the system from going blind.

## Retraining and drift plan

- Shadow mode first (4-8 weeks), then a pilot with a control group.
- Weekly: base rate, calibration, share of new operators, selection rates by office and transport, disagreement rate.
- Retrain monthly or when drift is detected; re-run this model card with every retraining.

## Contact

Team RAQIB - hackathon IA & Finances Publiques 2026 - https://github.com/yassinebennacef/RAQIB
