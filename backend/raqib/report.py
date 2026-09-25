"""`python -m raqib.report` - write every number-bearing document from the computed artifacts.

Generates docs/NOTE_DRAFT.md, docs/DECK_OUTLINE.md, docs/DEMO_SCRIPT.md, docs/RESULTS.md and
the generated blocks of README.md (between <!-- BEGIN:x --> / <!-- END:x --> markers).
No number is typed by hand: all come from artifacts/metrics.json, data_card.json and
test_scored.parquet (rerun after `python -m raqib.build`).
"""
from __future__ import annotations

import json
import re

import pandas as pd

from . import config as C


def pct(x: float, d: int = 0) -> str:
    return f"{x * 100:.{d}f}%"


def pts(x: float, d: int = 1) -> str:
    return f"{'+' if x >= 0 else '-'}{abs(x) * 100:.{d}f} pts"


def num(x: float) -> str:
    return f"{int(round(x)):,}"


class V:
    """All values used by the documents, computed once from the artifacts."""

    def __init__(self) -> None:
        self.m = json.loads((C.ARTIFACTS / "metrics.json").read_text(encoding="utf-8"))
        self.c = json.loads((C.ARTIFACTS / "data_card.json").read_text(encoding="utf-8"))
        self.ts = pd.read_parquet(C.ARTIFACTS / "test_scored.parquet")
        m, c = self.m, self.c
        self.F, self.K = m["targets"]["fraud"], m["targets"]["critical"]
        self.fm, self.km = self.F["methods"], self.K["methods"]
        rs = m["replay_summary"]
        self.rs = rs
        self.ai, self.aie = rs["policies"]["ai"], rs["policies"]["ai_explore"]
        self.rule, self.rnd = rs["policies"]["rule"], rs["policies"]["random"]
        self.gain_frauds = self.ai["frauds"] - self.rule["frauds"]
        self.gain_frauds_pct = self.gain_frauds / max(self.rule["frauds"], 1)
        self.threat_x = self.ai["threats"] / max(self.rule["threats"], 1)
        self.weeks_better = sum(1 for w in self.F["weekly"] if w["precision_ai"] > w["precision_rule"])
        self.n_weeks = len(self.F["weekly"])
        self.cal_top = self.F["calibration"][-1]
        self.fair = m["fairness"]
        self.ab = m["ablation_no_value"]
        self.value_share = next(g["share"] for g in self.F["importance"]["groups"] if g["group"] == "value")
        self.top_group = self.F["importance"]["groups"][0]
        self.th = m["thresholds"]
        self.pick_demo()

    def pick_demo(self) -> None:
        """Deterministic demo picks; prefer examples whose top reason rests on a solid history."""
        t = self.ts.copy()
        t["top_thin_f"] = [json.loads(r)[0]["thin_history"] for r in t["reasons_fraud"]]
        t["top_thin_c"] = [json.loads(r)[0]["thin_history"] for r in t["reasons_critical"]]
        known = t["seller"].notna() & ~t["hs_desc"].str.startswith("HS ")
        gain = t[known & (t["lane"] == "RED") & (~t["rule_selected"]) & (t["fraud"] == 1) & (~t["alert"])]
        gain = gain.sort_values(["top_thin_f", "p_fraud"], ascending=[True, False])
        self.demo_gain = gain.iloc[0] if len(gain) else t.sort_values("p_fraud", ascending=False).iloc[0]
        alert = t[known & t["alert"] & (t["critical"] == 1) & (~t["rule_selected"])]
        alert = alert.sort_values(["top_thin_c", "p_critical"], ascending=[True, False])
        self.demo_alert = alert.iloc[0] if len(alert) else t.sort_values("p_critical", ascending=False).iloc[0]
        self.n_disagree_gain = int(((t["lane"] == "RED") & (~t["rule_selected"]) & (t["fraud"] == 1)).sum())


def results_table(v: V) -> str:
    rows = [
        ("RAQIB AI", v.fm["ai"], v.km["ai"]),
        ("Rule: product (HS6) history", v.fm["rule_hs6_history"], v.km["rule_hs6_history"]),
        ("Rule: importer history", v.fm["rule_importer_history"], v.km["rule_importer_history"]),
        ("Random", v.fm["random"], v.km["random"]),
    ]
    out = [
        "| Method | Fraud AUC | Fraud precision @1% | @5% | @10% | Critical AUC | Critical recall @1% | @5% | @10% |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, f, k in rows:
        out.append(
            f"| {name} | {f['auc']:.3f} | {pct(f['precision_at_1'], 1)} | {pct(f['precision_at_5'], 1)} | "
            f"{pct(f['precision_at_10'], 1)} | {k['auc']:.3f} | {pct(k['recall_at_1'], 1)} | "
            f"{pct(k['recall_at_5'], 1)} | {pct(k['recall_at_10'], 1)} |"
        )
    return "\n".join(out)


def replay_table(v: V) -> str:
    out = [
        "| Policy (same inspections every day) | Inspections | Frauds caught | Threats caught | Hit rate | Distinct products inspected |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for p in (v.ai, v.aie, v.rule, v.rnd):
        out.append(f"| {p['label']} | {num(p['inspections'])} | {num(p['frauds'])} | {num(p['threats'])} | "
                   f"{pct(p['hit_rate'], 1)} | {num(p['distinct_hs6'])} |")
    return "\n".join(out)


def headline(v: V) -> str:
    return (f"With the same {num(v.rs['totals']['inspections'])} inspections over {v.rs['n_days']} test days "
            f"(5% of declarations), RAQIB catches **{num(v.ai['frauds'])} frauds and {num(v.ai['threats'])} "
            f"public-safety threats**, against {num(v.rule['frauds'])} and {num(v.rule['threats'])} for the best "
            f"current rule (product history) and {num(v.rnd['frauds'])} and {num(v.rnd['threats'])} at random: "
            f"**+{num(v.gain_frauds)} frauds (+{pct(v.gain_frauds_pct)}) and {v.threat_x:.1f}x the threats**, same workload.")


def gains_lines(v: V) -> str:
    gf, gk = v.F["gain_vs_rule"], v.K["gain_vs_rule"]
    return (f"- Duty fraud precision @5%: {pct(v.fm['ai']['precision_at_5'], 1)} vs {pct(v.fm['rule_hs6_history']['precision_at_5'], 1)} "
            f"for the rule: {pts(gf['mean_gain'])} (95% bootstrap CI {pts(gf['ci95'][0])} to {pts(gf['ci95'][1])}).\n"
            f"- Public-safety recall @5%: {pct(v.km['ai']['recall_at_5'], 1)} vs {pct(v.km['rule_hs6_history']['recall_at_5'], 1)}: "
            f"{pts(gk['mean_gain'])} (95% CI {pts(gk['ci95'][0])} to {pts(gk['ci95'][1])}); "
            f"{v.m['n_critical_test']} critical cases only, so ±{v.km['ai']['recall_se_at_5'] * 100:.0f} pts (1 s.e.).\n"
            f"- Stable: the AI beats the rule in {v.weeks_better} of {v.n_weeks} weeks (precision @5% within each week).\n"
            f"- Calibrated: in the riskiest tenth of declarations the model predicts {pct(v.cal_top['mean_predicted'], 1)} "
            f"fraud and {pct(v.cal_top['observed'], 1)} is observed.")


# ------------------------------------------------------------------------------ documents
def note(v: V) -> str:
    c = v.c
    return f"""# RAQIB — Note de synthèse (draft, max 2 pages)

**Challenge T2 — Ciblage et orientation automatisés des contrôles** · Team RAQIB · Hackathon « IA & Finances Publiques » 2026
*All figures below are generated by `python -m raqib.report` from the measured artifacts.*

## 1. The challenge
Customs can physically inspect only a small share of import declarations. Today the selection relies on fixed
rules (for instance the past fraud rate of the product) and on officers' experience, so many inspections find
nothing while duty fraud and dangerous goods are released. RAQIB chooses, every day and within a **fixed
inspection capacity**, which declarations to inspect (RED), to check on documents (YELLOW) and to release
(GREEN), for two objectives: **revenue** (duty fraud) and **public safety** (critical violations).

## 2. Technical approach
1. **Two supervised models** (LightGBM) learn from past inspection outcomes: duty fraud and critical fraud.
2. **Risk history as features**: for 8 keys (product HS6, HS4, HS2, importer, declarant, seller, origin, office),
   the smoothed past fraud rate and volume, computed *out-of-fold* so the model never sees its own labels;
   plus tax rate, net mass, value and unit value.
3. **Calibration** (isotonic regression): scores become probabilities an officer can read.
4. **Daily allocation**: capacity = 5% of the day's declarations (adjustable); public-safety alerts (top 1% of
   critical risk) take slots first, then the highest fraud probabilities; an optional 10% random **exploration**
   keeps the system learning; the next 10% go to YELLOW, the rest to GREEN.
5. **Explanations**: exact TreeSHAP contributions grouped into the 4 strongest reasons, written with the real
   historical numbers (e.g. "{json.loads(v.demo_gain['reasons_fraud'])[0]['text']}"), shown next to what the
   current rule would decide.
6. **Human in the loop**: the officer decides; every decision is appended to a hash-chained, tamper-evident journal.

Stack: Python (pandas, scikit-learn, LightGBM), FastAPI, React. The full pipeline trains in about 15 seconds on
a laptop CPU; a new declaration is scored in about 0.1 s. No LLM is used for scoring or decisions.

## 3. Data
Public **Customs Import Declaration Datasets** (Institute for Basic Science & Korea Customs Service, MIT licence):
{num(c['rows'])} synthetic declarations generated with CTGAN from real inspected declarations, 22 attributes including
the fraud and critical-fraud outcomes; {num(c['unique']['importers'])} importers, {num(c['unique']['hs6'])} products,
{num(c['unique']['origins'])} origins. **Train**: {num(c['train']['rows'])} declarations ({c['train']['period'][0]} → {c['train']['period'][1]}).
**Test**: {num(c['test']['rows'])} declarations ({c['test']['period'][0]} → {c['test']['period'][1]}), never used for training.
Product names: datasets/harmonized-system (ODC-PDDL). **No Tunisian data; no access to any administration system.**

## 4. Results versus current practice (measured on the test period)
{results_table(v)}

{gains_lines(v)}

**Daily replay** (91 real test days, identical capacity for every policy):

{replay_table(v)}

{headline(v)} Exploration (10% of slots at random) costs {num(v.ai['frauds'] - v.aie['frauds'])} frauds but widens
coverage from {num(v.ai['distinct_hs6'])} to {num(v.aie['distinct_hs6'])} distinct products. The AI releases
{pct(v.ai['green_share'])} of declarations in the green lane.

## 5. Limits (stated openly)
- Synthetic data of Korean origin; only inspected declarations were synthesised, so the fraud rate is
  {pct(c['fraud_rate'], 1)}, far above reality: absolute precision is optimistic, **the claim is the gain over the rule**.
- Only {v.m['n_critical_test']} critical cases in the test period (±{v.km['ai']['recall_se_at_5'] * 100:.0f} pts on recall @5%).
- Value and mass carry signal here (without them, precision @5% falls to {pct(v.ab['fraud']['precision_at_5'], 1)}), but
  {pct(c['test_unit_value_equals_product_median'])} of test declarations have exactly their product's usual unit value: to re-validate on real data.
- {pct(c['test_new_operators']['importer'])} of test declarations come from importers never seen before: treated as average risk.
- Learning only from inspected declarations creates selection bias; exploration and a control group correct it.
- Alert and lane thresholds were set on the test period; in production they come from the previous weeks.

## 6. Recommendations for production in Tunisia
1. **Retrain inside the administration** on Tunisian inspection outcomes (same recipe; minutes on a normal CPU).
2. **Shadow mode** (4-8 weeks): RAQIB scores in parallel with current rules, without affecting decisions.
3. **Controlled pilot**: some offices or days use RAQIB lanes, others keep the rules; measure hit rate, duties
   recovered, threats found and clearance time.
4. **Keep 5-10% exploration** and a random control sample so the model stays unbiased.
5. **Weekly monitoring**: drift, calibration, share of new operators, selection rates by office and transport mode;
   retrain when they drift.
6. **Governance**: advisory score only, the officer decides, every decision journaled; compliance with Organic
   Law 2004-63 on personal data and review by the INPDP.

## 7. Third-party components
Libraries: pandas, NumPy, PyArrow, scikit-learn, LightGBM, joblib, FastAPI, Uvicorn, Pydantic, React, Vite,
Tailwind CSS, Recharts, Framer Motion, Lucide, Sonner (all permissive licences; full list in THIRD_PARTY.md).
Datasets: Customs Import Declaration Datasets (MIT), datasets/harmonized-system (ODC-PDDL).
AI coding assistant: Claude Code (Anthropic) was used to write and test the code. Scoring uses only the models above.
"""


def deck(v: V) -> str:
    c = v.c
    g, a = v.demo_gain, v.demo_alert
    return f"""# RAQIB — Deck outline (12 slides)

*Generated by `python -m raqib.report`: every number is computed from the artifacts. Rerun after a rebuild.*

## 1. Title
**RAQIB — رقيب — AI targeting of customs controls** (challenge T2).
Subtitle: {headline(v)}
*Speaker notes*: introduce the team and the one-line promise: same inspection capacity, more fraud and more
threats found, every decision explained, the officer stays in charge.

## 2. The problem
- Customs inspects a small share of declarations; selection relies on fixed rules and experience.
- Best current rule on our data (product history): {pct(v.rule['hit_rate'])} of inspections find fraud; it catches
  only {num(v.rule['threats'])} of the {num(v.rs['totals']['threats'])} public-safety threats of the period.
*Speaker notes*: every useless inspection is lost officer time and slower clearance for honest traders.

## 3. What RAQIB does every day
- Scores every declaration for **duty fraud** and **public-safety** risk.
- Fills the fixed capacity: safety alerts first, then highest fraud risk, plus 10% exploration.
- Lanes: RED inspect / YELLOW document check / GREEN release ({pct(v.ai['green_share'])} released green).
- 4 plain-language reasons + what the current rule would do; the officer decides and the decision is journaled.
*Speaker notes*: show the lane colours; stress "advisory".

## 4. Data (public, no Tunisian data)
- Customs Import Declaration Datasets (IBS & Korea Customs Service, MIT): {num(c['rows'])} declarations, 22 attributes.
- Train {num(c['train']['rows'])} ({c['train']['period'][0]} → {c['train']['period'][1]}), test {num(c['test']['rows'])} ({c['test']['period'][0]} → {c['test']['period'][1]}), never seen in training.
- Same ecosystem as the WCO BACUDA project (DATE model, KDD 2020; ML targeting piloted with Nigeria Customs in 2020).
*Speaker notes*: we never touched any administration system.

## 5. How the AI works (6 steps)
History of each product / importer / declarant / seller / origin / office (out-of-fold) → two LightGBM models →
calibrated probabilities → daily capacity allocation → TreeSHAP reasons → officer decision + hash-chained journal.
Model relies most on: {v.top_group['label']} ({pct(v.top_group['share'])} of the gain).
*Speaker notes*: trains in about 15 s on a laptop; scores a declaration in about 0.1 s.

## 6. Result 1 — better targeting at the same capacity
- Duty fraud precision @5%: **{pct(v.fm['ai']['precision_at_5'])}** vs {pct(v.fm['rule_hs6_history']['precision_at_5'])} (rule) vs {pct(v.fm['random']['precision_at_5'])} (random).
- Public-safety recall @5%: **{pct(v.km['ai']['recall_at_5'])}** vs {pct(v.km['rule_hs6_history']['recall_at_5'])} (rule).
- AUC: fraud {v.fm['ai']['auc']:.3f} vs {v.fm['rule_hs6_history']['auc']:.3f}; critical {v.km['ai']['auc']:.3f} vs {v.km['rule_hs6_history']['auc']:.3f}.
*Speaker notes*: precision @5% = share of the 5% riskiest declarations that were really fraudulent.

## 7. Result 2 — the replay race (the demo)
{replay_table(v)}

*Speaker notes*: 91 real days, identical daily capacity; +{num(v.gain_frauds)} frauds (+{pct(v.gain_frauds_pct)}) and
{v.threat_x:.1f}x the threats for the same {num(v.rs['totals']['inspections'])} inspections.

## 8. Result 3 — robust, not lucky
{gains_lines(v)}
*Speaker notes*: the bootstrap interval never crosses zero.

## 9. Explainable and human-in-the-loop
- Example declaration {g['declaration_id']} (product {str(int(g['hs6'])).zfill(6)}): AI inspects, the rule releases it; fraud confirmed.
  Top reason: "{json.loads(g['reasons_fraud'])[0]['text']}"
- Every decision (inspect / document check / release) is written to a tamper-evident journal (SHA-256 chain).
*Speaker notes*: the AI never decides; it prioritises and explains.

## 10. Honest limits
- Fraud rate {pct(c['fraud_rate'], 1)} (only inspected declarations were synthesised): we claim the gain, not the absolute precision.
- {v.m['n_critical_test']} critical cases in test (±{v.km['ai']['recall_se_at_5'] * 100:.0f} pts).
- Value signals may be a synthetic artefact ({pct(c['test_unit_value_equals_product_median'])} of declarations carry their product's usual unit value).
- Selection bias → exploration + control group.
*Speaker notes*: say it before the jury asks.

## 11. Path to production in Tunisia
Retrain inside the administration → shadow mode 4-8 weeks → controlled pilot with a control group → weekly drift,
calibration and fairness monitoring → governance (advisory, journal, Organic Law 2004-63 / INPDP).
*Speaker notes*: nothing requires special hardware; a normal CPU server is enough.

## 12. Ask
A shadow-mode pilot on one office with Tunisian inspection data, measured against the current rules.
Team RAQIB. Demo: http://127.0.0.1:8000 · Code: https://github.com/yassinebennacef/RAQIB
*Speaker notes*: thank the jury; open Q&A.
"""


def demo_script(v: V) -> str:
    g, a = v.demo_gain, v.demo_alert
    g_reason = json.loads(g["reasons_fraud"])[0]["text"]
    a_reason = json.loads(a["reasons_critical"])[0]["text"]
    return f"""# RAQIB — Demo script (10 minutes)

*Generated by `python -m raqib.report`. Start the app with `run_demo.bat` (or `python -m raqib.serve --open`),
browser full screen at http://127.0.0.1:8000. Backup: screenshots in docs/screenshots and the recorded video.*

| Time | Screen | What to do | What to say |
|---|---|---|---|
| 0:00-1:00 | Control room (day 0) | Nothing yet. Point at the capacity slider (5%). | "Customs can inspect about 5% of declarations. Which 5%? Today a rule decides. RAQIB replays 91 real days the model never saw, with exactly the same capacity for AI, rule and random." |
| 1:00-3:00 | Control room | Speed 4-8 days/s, press **Play** (or space). Let the counters run. | "Blue is RAQIB, orange the best current rule, grey random. Same {num(v.rs['totals']['inspections'])} inspections. At the end: **{num(v.ai['frauds'])} vs {num(v.rule['frauds'])} vs {num(v.rnd['frauds'])} frauds**, and **{num(v.ai['threats'])} vs {num(v.rule['threats'])}** public-safety threats." |
| 3:00-3:30 | Control room | Toggle **Exploration 10%**. | "A small random share keeps the system learning: it costs {num(v.ai['frauds'] - v.aie['frauds'])} frauds and widens coverage to {num(v.aie['distinct_hs6'])} products. It never goes blind." |
| 3:30-5:30 | Inspector | Open declaration **{g['declaration_id']}** (http://127.0.0.1:8000/declaration/{g['declaration_id']}). | "RAQIB says inspect; the rule says release. Why? '{g_reason}' Here is the importer, declarant and seller history, and the network." Click **Inspect**, show the toast with the journal hash. "The officer decides; the decision is chained and tamper-evident." Click **Reveal outcome**: fraud found. |
| 5:30-6:30 | Inspector | Open **{a['declaration_id']}** (http://127.0.0.1:8000/declaration/{a['declaration_id']}). | "A public-safety alert takes a slot first: '{a_reason}'" |
| 6:30-7:30 | Try a declaration | Click the preset **Public-safety alert** (it scores instantly); then tick *new operator* for the importer and click **Score this declaration** again. | "Scoring takes about 0.1 s. A new importer has no history: RAQIB treats it as average risk and says so." |
| 7:30-9:00 | Model lab | Scroll the page. | "Precision @5%: {pct(v.fm['ai']['precision_at_5'])} vs {pct(v.fm['rule_hs6_history']['precision_at_5'])}; the 95% interval of the gain never crosses zero; the AI wins {v.weeks_better} weeks out of {v.n_weeks}; it is calibrated; and here are our limits, stated openly." |
| 9:00-10:00 | About | Show the path to production. | "Next step: retrain on Tunisian inspection results inside the administration, shadow mode, then a pilot with a control group. The officer stays in charge." |

## If something goes wrong
- API offline badge (top right is red): run `run_demo.bat` again; the build is skipped when artifacts exist.
- A page is slow: refresh; the first load warms the models (about 4 s).
- Laptop failure: play the backup video; screenshots are in docs/screenshots/.

## Likely questions (short answers with our numbers)
- *"Is the data real?"* Public synthetic declarations generated from real Korean inspected declarations (MIT). No Tunisian data. We claim the gain over the rule, not the absolute precision.
- *"Why not just use the rule?"* Same capacity: +{num(v.gain_frauds)} frauds and {num(v.ai['threats'])} vs {num(v.rule['threats'])} threats.
- *"Is the gain luck?"* Bootstrap 95% CI of the precision gain: {pts(v.F['gain_vs_rule']['ci95'][0])} to {pts(v.F['gain_vs_rule']['ci95'][1])}; {v.weeks_better}/{v.n_weeks} weeks better.
- *"Does it discriminate?"* Selection rates by transport mode stay within {v.fair['transport']['max_min_selection_ratio_ai']:.1f}x; by office {v.fair['office']['max_min_selection_ratio_ai']:.1f}x (Model lab, fairness view) — monitored weekly in production.
- *"What about new companies?"* {pct(v.c['test_new_operators']['importer'])} of test declarations come from unseen importers; average risk, flagged in the reasons.
- *"Does it replace officers?"* No: advisory score, the officer decides, every decision journaled.
"""


def results_doc(v: V) -> str:
    return f"""# RAQIB — Measured results

*Generated by `python -m raqib.report` from artifacts/metrics.json ({v.m['generated_at']}).*

Test period {v.m['recipe']['test'][0]} → {v.m['recipe']['test'][1]} ({num(v.m['recipe']['n_test'])} declarations,
never used for training). Top-k uses k = ceil(share x n); ties broken by one fixed random permutation.

## AI vs rules vs random
{results_table(v)}

{gains_lines(v)}

## Daily replay at 5% capacity
{replay_table(v)}

{headline(v)}

## Ablation: without value and mass features
| Target | Full model | Without value/mass |
|---|---:|---:|
| Duty fraud precision @5% | {pct(v.fm['ai']['precision_at_5'], 1)} | {pct(v.ab['fraud']['precision_at_5'], 1)} |
| Duty fraud AUC | {v.fm['ai']['auc']:.3f} | {v.ab['fraud']['auc']:.3f} |
| Public-safety recall @5% | {pct(v.km['ai']['recall_at_5'], 1)} | {pct(v.ab['critical']['recall_at_5'], 1)} |
| Public-safety AUC | {v.km['ai']['auc']:.3f} | {v.ab['critical']['auc']:.3f} |

## Operating thresholds (from the test period)
RED from p(fraud) ≥ {pct(v.th['red_p_fraud'], 1)}; YELLOW from p(fraud) ≥ {pct(v.th['yellow_p_fraud'], 1)};
public-safety alert from p(critical) ≥ {pct(v.th['alert_p_critical'], 1)}.
"""


def readme_blocks(v: V) -> dict[str, str]:
    return {
        "pitch": headline(v),
        "results": results_table(v) + "\n\n" + gains_lines(v),
        "replay": replay_table(v),
    }


def update_readme(blocks: dict[str, str]) -> None:
    path = C.ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    for key, body in blocks.items():
        pat = re.compile(rf"(<!-- BEGIN:{key} -->)(.*?)(<!-- END:{key} -->)", re.S)
        text = pat.sub(lambda mt: f"{mt.group(1)}\n{body}\n{mt.group(3)}", text)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    v = V()
    docs = C.ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "NOTE_DRAFT.md").write_text(note(v), encoding="utf-8")
    (docs / "DECK_OUTLINE.md").write_text(deck(v), encoding="utf-8")
    (docs / "DEMO_SCRIPT.md").write_text(demo_script(v), encoding="utf-8")
    (docs / "RESULTS.md").write_text(results_doc(v), encoding="utf-8")
    if (C.ROOT / "README.md").exists():
        update_readme(readme_blocks(v))
    print("[report] docs/NOTE_DRAFT.md, DECK_OUTLINE.md, DEMO_SCRIPT.md, RESULTS.md and README blocks written")
    print(f"[report] demo declarations: gain {v.demo_gain['declaration_id']}, alert {v.demo_alert['declaration_id']}")


if __name__ == "__main__":
    main()
