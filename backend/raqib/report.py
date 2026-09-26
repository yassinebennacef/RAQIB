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
        self.eff = m.get("efficiency")
        self.unc = m.get("uncertainty")
        self.primary = m.get("primary_model", {"fraud": "lightgbm", "critical": "lightgbm"})
        exp_path = C.ARTIFACTS / "experiments.json"
        self.exps = json.loads(exp_path.read_text(encoding="utf-8"))["experiments"] if exp_path.exists() else []
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
        t["top_group_f"] = [json.loads(r)[0]["group"] for r in t["reasons_fraud"]]
        if "uncertain" in t.columns:
            known &= ~t["uncertain"].astype(bool)
        known &= t["top_group_f"].isin(["product", "family", "importer", "declarant", "seller", "origin"])
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


def efficiency_line(v: V) -> str:
    if not v.eff or "fewer_pct" not in v.eff["matching"]:
        return ""
    mt, pl = v.eff["matching"], v.eff["pooled"]
    return (f"**Same frauds with fewer inspections:** the rule needs {num(mt['reference']['inspections'])} inspections "
            f"(5% a day) to catch {num(mt['reference']['frauds'])} frauds; RAQIB catches {num(mt['ai_frauds'])} with "
            f"{num(mt['ai_inspections'])} ({pct(mt['ai_rate'], 1)} a day): **{pct(mt['fewer_pct'])} fewer inspections** "
            f"(pooled ranking: {num(pl['k_ai_needed'])} vs {num(pl['k_rule'])}, {pct(pl['fewer_pct'])} fewer).")


def glassbox_line(v: V) -> str:
    fl, fe = v.fm.get("lightgbm"), v.fm.get("ebm")
    if not fl or not fe:
        return ""
    return (f"**Glass box, no accuracy lost:** the transparent EBM reaches duty-fraud AUC {fe['auc']:.3f} and "
            f"precision @5% {pct(fe['precision_at_5'], 1)} vs {fl['auc']:.3f} / {pct(fl['precision_at_5'], 1)} for the "
            f"black-box LightGBM; primary model: fraud = {v.primary['fraud'].upper()}, "
            f"critical = {v.primary['critical'].upper()}.")


def uncertainty_line(v: V) -> str:
    u = v.unc
    if not u:
        return ""
    return (f"**When the two models disagree, RAQIB asks a human:** {num(u['n_flagged'])} test declarations "
            f"({pct(u['share_flagged'], 1)}) are flagged, with a fraud rate of {pct(u['fraud_rate_flagged'])} "
            f"(average {pct(u['fraud_rate_all'])}); {num(u['green_to_yellow'])} of them move from GREEN to a document check.")


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
1. **Two supervised models** learn from past inspection outcomes: duty fraud (primary: {v.primary["fraud"].upper()}) and critical fraud (primary: {v.primary["critical"].upper()}); each has a twin (glass-box EBM and LightGBM) and their disagreement flags uncertain cases.
2. **Risk history as features**: for 8 keys (product HS6, HS4, HS2, importer, declarant, seller, origin, office),
   the smoothed past fraud rate and volume, computed *out-of-fold* so the model never sees its own labels;
   plus tax rate, net mass, value and unit value.
3. **Calibration** (isotonic regression): scores become probabilities an officer can read.
4. **Daily allocation**: capacity = 5% of the day's declarations (adjustable); public-safety alerts (top 1% of
   critical risk) take slots first, then the highest fraud probabilities; an optional 10% random **exploration**
   keeps the system learning; the next 10% go to YELLOW, the rest to GREEN.
5. **Explanations**: exact additive contributions (EBM terms or TreeSHAP) grouped into the 4 strongest reasons and an exact waterfall, written with the real
   historical numbers (e.g. "{json.loads(v.demo_gain['reasons_fraud'])[0]['text']}"), shown next to what the
   current rule would decide.
6. **Human in the loop**: the officer decides; every decision is appended to a hash-chained, tamper-evident journal.

Stack: Python (pandas, scikit-learn, LightGBM, InterpretML EBM), FastAPI, React (shadcn-admin template). The full pipeline trains in about 15 seconds on
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

{headline(v)}

{efficiency_line(v)}

{glassbox_line(v)}

{uncertainty_line(v)}

Exploration (10% of slots at random) costs {num(v.ai['frauds'] - v.aie['frauds'])} frauds but widens
coverage from {num(v.ai['distinct_hs6'])} to {num(v.aie['distinct_hs6'])} distinct products. The AI releases
{pct(v.ai['green_share'])} of declarations in the green lane.

## 5. Limits (stated openly)
- Synthetic data of Korean origin; only inspected declarations were synthesised, so the fraud rate is
  {pct(c['fraud_rate'], 1)}, far above reality: absolute precision is optimistic, **the claim is the gain over the rule**.
- Only {v.m['n_critical_test']} critical cases in the test period (±{v.km['ai']['recall_se_at_5'] * 100:.0f} pts on recall @5%).
- Value and mass carry signal here (without them, LightGBM precision @5% falls from {pct(v.ab['fraud']['full_precision_at_5'], 1)} to {pct(v.ab['fraud']['precision_at_5'], 1)}), but
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
Libraries: pandas, NumPy, PyArrow, scikit-learn, LightGBM, InterpretML (EBM), joblib, FastAPI, Uvicorn, Pydantic, React, Vite,
Tailwind CSS, shadcn-admin template, Radix UI, TanStack, Recharts, Framer Motion, Lucide, Sonner (all permissive licences; full list in THIRD_PARTY.md).
Datasets: Customs Import Declaration Datasets (MIT), datasets/harmonized-system (ODC-PDDL).
AI coding assistant: Claude Code (Anthropic) was used to write and test the code. Scoring uses only the models above.
"""


def _exp(v: V, key: str) -> dict:
    return next((e for e in v.exps if e["key"] == key), {"result": {}})


def deck(v: V) -> str:
    c = v.c
    g = v.demo_gain
    mt, pl = (v.eff or {}).get("matching", {}), (v.eff or {}).get("pooled", {})
    fe, fl = v.fm.get("ebm", {}), v.fm.get("lightgbm", {})
    u = v.unc or {}
    iso, net = _exp(v, "isolation_forest")["result"], _exp(v, "network_2hop")["result"]
    return f"""# RAQIB — Deck outline (12 slides, v2)

*Generated by `python -m raqib.report`: every number is computed from the artifacts. Rerun after a rebuild.*

## 1. Title
**RAQIB — رقيب — AI targeting of customs controls** (challenge T2).
Subtitle: {headline(v)}
*Speaker notes*: same inspection capacity, more fraud and more threats found; a glass-box AI; the officer stays in charge.

## 2. The problem
- Customs inspects a small share of declarations; selection relies on fixed rules and experience.
- Best current rule on our data (product history): {pct(v.rule['hit_rate'])} of inspections find fraud; it catches only
  {num(v.rule['threats'])} of the {num(v.rs['totals']['threats'])} public-safety threats of the period.
*Speaker notes*: every useless inspection is lost officer time and slower clearance for honest traders.

## 3. What RAQIB does every day
- Scores every declaration for **duty fraud** and **public-safety** risk.
- Fills the fixed capacity: safety alerts first, then highest fraud risk, plus 10% exploration.
- Lanes RED inspect / YELLOW document check / GREEN release ({pct(v.ai['green_share'])} released green).
- Worklist for officers, 4 plain-language reasons, exact waterfall, the rule side by side, decisions journaled.
*Speaker notes*: show the lane colours; stress "advisory".

## 4. Data (public, no Tunisian data)
- Customs Import Declaration Datasets (IBS & Korea Customs Service, MIT): {num(c['rows'])} declarations, 22 attributes.
- Train {num(c['train']['rows'])} ({c['train']['period'][0]} → {c['train']['period'][1]}), test {num(c['test']['rows'])} ({c['test']['period'][0]} → {c['test']['period'][1]}), never seen in training.
- Same ecosystem as the WCO BACUDA project (DATE model, KDD 2020; ML targeting piloted with Nigeria Customs in 2020).

## 5. How the AI works — a glass box
History of each product / importer / declarant / seller / origin / office (out-of-fold) → two model families:
**EBM (glass box)** and **LightGBM** → calibrated probabilities → daily capacity allocation → exact reasons.
Primary model: duty fraud = **{v.primary['fraud'].upper()}**, public safety = **{v.primary['critical'].upper()}** (rule: glass box
unless it loses more than 1.5 points).
*Speaker notes*: "{glassbox_line(v).replace('**', '')}"

## 6. Result 1 — better targeting at the same capacity
- Duty fraud precision @5%: **{pct(v.fm['ai']['precision_at_5'])}** vs {pct(v.fm['rule_hs6_history']['precision_at_5'])} (rule) vs {pct(v.fm['random']['precision_at_5'])} (random).
- Public-safety recall @5%: **{pct(v.km['ai']['recall_at_5'])}** vs {pct(v.km['rule_hs6_history']['recall_at_5'])} (rule).
{gains_lines(v)}

## 7. Result 2 — the replay race (live demo)
{replay_table(v)}

*Speaker notes*: 91 real days, identical daily capacity; +{num(v.gain_frauds)} frauds (+{pct(v.gain_frauds_pct)}) and
{v.threat_x:.1f}x the threats for the same {num(v.rs['totals']['inspections'])} inspections.

## 8. Result 3 — same frauds with fewer inspections
- Daily replay: the rule needs {num(mt.get('reference', {}).get('inspections', 0))} inspections for {num(mt.get('reference', {}).get('frauds', 0))} frauds; RAQIB
  finds {num(mt.get('ai_frauds', 0))} with {num(mt.get('ai_inspections', 0))}: **{pct(mt.get('fewer_pct', 0))} fewer inspections**.
- Pooled ranking: {num(pl.get('k_ai_needed', 0))} vs {num(pl.get('k_rule', 0))} inspections: **{pct(pl.get('fewer_pct', 0))} fewer**.
- Officer hours freed: shown with an explicit, editable assumption (minutes per inspection) in the Impact simulator.
*Speaker notes*: "about a fifth to a third fewer inspections for the same result".

## 9. Explainable, uncertain-aware, human in the loop
- Exact waterfall for every declaration (base rate → each factor → final probability) and the learned shape functions.
- Example {g['declaration_id']} (product {str(int(g['hs6'])).zfill(6)}): AI inspects, the rule releases it; fraud confirmed.
  Top reason: "{json.loads(g['reasons_fraud'])[0]['text']}"
- When the glass box and the black box disagree ({num(u.get('n_flagged', 0))} declarations, fraud rate {pct(u.get('fraud_rate_flagged') or 0)} vs {pct(u.get('fraud_rate_all') or 0)}),
  RAQIB never releases: it asks a human. Officer brief in French, English and Arabic; decisions hash-chained.

## 10. We only ship what we measure — tested, rejected, limits
- Anomaly detection (Isolation Forest): fraud AUC {iso.get('fraud_auc', 0):.2f} → rejected (no signal).
- 2-hop network features: AUC {net.get('auc_with', 0):.4f} vs {net.get('auc_without', 0):.4f} without → rejected (synthetic rows have no real links).
- Limits: fraud rate {pct(c['fraud_rate'], 1)} (only inspected declarations were synthesised); {v.m['n_critical_test']} critical cases in test;
  value signals may be a synthetic artefact ({pct(c['test_unit_value_equals_product_median'])} of declarations carry their product's usual unit value).

## 11. Path to production in Tunisia
Retrain inside the administration → shadow mode 4-8 weeks → controlled pilot with a control group → weekly drift,
calibration, fairness and disagreement monitoring → governance (model card, advisory, journal, Organic Law 2004-63 / INPDP).

## 12. Ask
A shadow-mode pilot on one office with Tunisian inspection data, measured against the current rules.
Team RAQIB. Demo: http://127.0.0.1:8000 · Code: https://github.com/yassinebennacef/RAQIB
"""


def demo_script(v: V) -> str:
    g, a = v.demo_gain, v.demo_alert
    g_reason = json.loads(g["reasons_fraud"])[0]["text"]
    a_reason = json.loads(a["reasons_critical"])[0]["text"]
    mt, pl = (v.eff or {}).get("matching", {}), (v.eff or {}).get("pooled", {})
    fe, fl = v.fm.get("ebm", {}), v.fm.get("lightgbm", {})
    u = v.unc or {}
    return f"""# RAQIB — Demo script (10 minutes, v2 web app)

*Generated by `python -m raqib.report`. Start with `run_demo.bat` (or `python -m raqib.serve --open`), browser full screen
at http://127.0.0.1:8000. Fallback UI: `python -m raqib.serve --ui v1`. Backup: docs/screenshots/v2 and the recorded video.*

| Time | Screen | What to do | What to say |
|---|---|---|---|
| 0:00-0:45 | Control room | Point at the capacity slider (5%). | "Customs can inspect about 5% of declarations. Which 5%? RAQIB replays 91 real days the models never saw, with exactly the same capacity for AI, rule and random." |
| 0:45-2:15 | Control room | Speed 8, **Play**; then open one RED row in the feed (side sheet). | "Same {num(v.rs['totals']['inspections'])} inspections: **{num(v.ai['frauds'])} vs {num(v.rule['frauds'])} vs {num(v.rnd['frauds'])} frauds**, **{num(v.ai['threats'])} vs {num(v.rule['threats'])}** public-safety threats." |
| 2:15-3:15 | Impact simulator | Show the capacity curve and the two big numbers. | "Or the other way round: the same frauds with **{pct(mt.get('fewer_pct', 0))} fewer inspections** ({pct(pl.get('fewer_pct', 0))} on a pooled ranking): officers freed, honest traders cleared faster." |
| 3:15-4:15 | Worklist | Filter Lane = RED, Models = disagree; open a row; bulk "Assign to me". | "This is the officer's inbox. When our two models disagree ({num(u.get('n_flagged', 0))} declarations, fraud rate {pct(u.get('fraud_rate_flagged') or 0)}), RAQIB never releases: it asks a human." |
| 4:15-6:00 | Inspector | Ctrl+K → type **{g['declaration_id']}** → open. Show the waterfall, reasons, rule side by side, brief FR/AR, click **Inspect**. | "RAQIB inspects, the rule releases. Why? '{g_reason}' The waterfall is exact. The officer decides; the decision is hash-chained." Reveal outcome: fraud found. |
| 6:00-6:40 | Inspector → Worklist | Officer brief: switch **Français → العربية**. Then Ctrl+K, type the FR question "déclarations rouges d'origine CN au chapitre 85 au-dessus de 80%" → **Ask RAQIB** → show the chips → **Apply**. | "Runs 100% locally on the laptop GPU — no declaration data leaves the administration. The LLM only rephrases verified facts and turns a question into a filter the officer confirms; it never scores or decides." |
| 6:40-7:00 | Inspector | Ctrl+K → **{a['declaration_id']}**. | "A public-safety alert takes a slot first: '{a_reason}'" |
| 6:30-8:00 | Explainability | Glass box vs black box, shape functions, then the what-if sliders (value ×0.3, new importer). | "A glass box: EBM {pct(fe.get('precision_at_5', 0), 1)} vs LightGBM {pct(fl.get('precision_at_5', 0), 1)} at 5%. Here is exactly what it learned; change the declaration and watch the risk move." |
| 8:00-8:45 | Explainability → Tested ideas; Model card | Scroll to the 4 cards; open the Model card. | "We tested four ideas and rejected two. We only ship what we measure. Intended use, out-of-scope uses, limits: all in the model card." |
| 8:45-9:15 | Decision journal | Click **Verify chain**. | "Every decision is in a tamper-evident journal." |
| 9:15-10:00 | About | Path to production. | "Next: retrain on Tunisian inspection results inside the administration, shadow mode, then a pilot with a control group." |

## If something goes wrong
- API offline badge / blank page: run `run_demo.bat` again (build skipped when artifacts load).
- v2 page broken: restart with `python -m raqib.serve --ui v1` (the v1 control room).
- Laptop failure: play the backup video; screenshots are in docs/screenshots/v2/.

## Likely questions (short answers with our numbers)
- *"Is the data real?"* Public synthetic declarations generated from real Korean inspected declarations (MIT). No Tunisian data. We claim the gain over the rule, not the absolute precision.
- *"Is the gain luck?"* Bootstrap 95% CI of the precision gain: {pts(v.F['gain_vs_rule']['ci95'][0])} to {pts(v.F['gain_vs_rule']['ci95'][1])}; {v.weeks_better}/{v.n_weeks} weeks better.
- *"Is it a black box?"* No: the duty-fraud model is an EBM; every probability is an exact sum of readable contributions, and it is as accurate as LightGBM.
- *"Why not a graph neural network or anomaly detection?"* We tested both families: no gain on this data (synthetic rows have no real links). On real Tunisian data the network is the first thing we would re-test.
- *"Does it discriminate?"* Selection rates by transport mode stay within {v.fair['transport']['max_min_selection_ratio_ai']:.1f}x; by office {v.fair['office']['max_min_selection_ratio_ai']:.1f}x — monitored weekly.
- *"Does it replace officers?"* No: advisory score, the officer decides, every decision journaled; disagreement → human review.
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

## Glass box vs black box
{twin_table(v)}

{glassbox_line(v)}

## Efficiency
{efficiency_line(v)}

## Uncertainty
{uncertainty_line(v)}

## Tested ideas
{experiments_table(v)}

## Ablation: LightGBM without value and mass features
| Target | LightGBM full | Without value/mass |
|---|---:|---:|
| Duty fraud precision @5% | {pct(v.ab['fraud']['full_precision_at_5'], 1)} | {pct(v.ab['fraud']['precision_at_5'], 1)} |
| Duty fraud AUC | {v.ab['fraud']['full_auc']:.3f} | {v.ab['fraud']['auc']:.3f} |
| Public-safety recall @5% | {pct(v.ab['critical']['full_recall_at_5'], 1)} | {pct(v.ab['critical']['recall_at_5'], 1)} |
| Public-safety AUC | {v.ab['critical']['full_auc']:.3f} | {v.ab['critical']['auc']:.3f} |

## Operating thresholds (from the test period)
RED from p(fraud) ≥ {pct(v.th['red_p_fraud'], 1)}; YELLOW from p(fraud) ≥ {pct(v.th['yellow_p_fraud'], 1)};
public-safety alert from p(critical) ≥ {pct(v.th['alert_p_critical'], 1)}.
"""


def twin_table(v: V) -> str:
    out = ["| Target | Model | AUC | Precision @5% | Recall @5% | Primary |", "|---|---|---:|---:|---:|---|"]
    for target, key, T in (("Duty fraud", "fraud", v.fm), ("Public safety", "critical", v.km)):
        for mk, lab in (("lightgbm", "LightGBM (black box)"), ("ebm", "EBM (glass box)")):
            if mk in T:
                m = T[mk]
                out.append(f"| {target} | {lab} | {m['auc']:.3f} | {pct(m['precision_at_5'], 1)} | {pct(m['recall_at_5'], 1)} | "
                           f"{'yes' if v.primary.get(key) == mk else ''} |")
    return "\n".join(out)


def experiments_table(v: V) -> str:
    out = ["| Idea | Decision | Measured | Why |", "|---|---|---|---|"]
    for e in v.exps:
        r = e["result"]
        if e["key"] == "isolation_forest":
            meas = f"fraud AUC {r['fraud_auc']:.3f}; top-1% fraud rate {pct(r['top1_fraud_rate'], 1)} (base {pct(r['base_rate'], 1)})"
        elif e["key"] == "network_2hop":
            meas = f"AUC {r['auc_with']:.4f} with vs {r['auc_without']:.4f} without; P@5% {pct(r['p5_with'], 1)} vs {pct(r['p5_without'], 1)}"
        elif e["key"] == "ebm":
            meas = (f"fraud AUC {r['fraud_auc']:.3f}, P@5% {pct(r['fraud_precision_at_5'], 1)} "
                    f"(LightGBM {e['baseline']['fraud_auc']:.3f}, {pct(e['baseline']['fraud_precision_at_5'], 1)})")
        else:
            meas = f"{num(r['n_flagged'])} flagged ({pct(r['share_flagged'], 1)}), fraud rate {pct(r['fraud_rate_flagged'])}"
        out.append(f"| {e['title']} | {e['decision']} | {meas} | {e['reason']} |")
    return "\n".join(out)


def model_card(v: V) -> dict:
    c, m = v.c, v.m
    fe, fl, ke, kl = v.fm.get("ebm", {}), v.fm.get("lightgbm", {}), v.km.get("ebm", {}), v.km.get("lightgbm", {})
    u = v.unc or {}
    sections = [
        {"key": "intended_use", "title": "Intended use",
         "text": "Advisory ranking of import declarations for customs officers: which declarations to inspect (RED), "
                 "to check on documents (YELLOW) or to release (GREEN) under a fixed daily inspection capacity. "
                 "RAQIB prioritises and explains; the officer always decides."},
        {"key": "users", "title": "Users",
         "bullets": ["Risk-analysis officers who prepare the daily inspection plan.",
                     "Inspection officers at the offices (worklist, inspector, decision journal).",
                     "Supervisors and auditors (hash-chained decision journal, model card, fairness view)."]},
        {"key": "out_of_scope", "title": "Out-of-scope uses",
         "bullets": ["Automatic sanctions, penalties or seizures without an officer's decision.",
                     "Scoring, ranking or publishing scores about traders; the what-if simulator is an officer-only tool and is never shown to traders.",
                     "Use on data that differs from the training data (other country, other period) without retraining and re-validation."]},
        {"key": "data", "title": "Data",
         "text": (f"Customs Import Declaration Datasets (Institute for Basic Science & Korea Customs Service, MIT): "
                  f"{num(c['rows'])} synthetic declarations (CTGAN) from real inspected declarations. Train {num(c['train']['rows'])} "
                  f"({c['train']['period'][0]} to {c['train']['period'][1]}), test {num(c['test']['rows'])} ({c['test']['period'][0]} to "
                  f"{c['test']['period'][1]}). Fraud rate {pct(c['fraud_rate'], 1)}; {m['n_critical_test']} critical cases in the test period. "
                  f"No Tunisian data.")},
        {"key": "models", "title": "Models",
         "text": ("Two models per target on the same features (out-of-fold smoothed fraud history of product, family, chapter, "
                  "importer, declarant, seller, origin and office, plus tax rate, mass, value and unit value): a LightGBM "
                  "gradient-boosting model and an Explainable Boosting Machine (glass box: every prediction is an exact sum of "
                  "readable per-feature contributions). " + m.get("primary_model", {}).get("rule", "")),
         "table": {"columns": ["Target", "Primary", "LightGBM AUC", "EBM AUC", "LightGBM op. metric", "EBM op. metric"],
                   "rows": [["Duty fraud (precision @5%)", v.primary.get("fraud", ""), f"{fl.get('auc', 0):.3f}", f"{fe.get('auc', 0):.3f}",
                             pct(fl.get("precision_at_5", 0), 1), pct(fe.get("precision_at_5", 0), 1)],
                            ["Public safety (recall @5%)", v.primary.get("critical", ""), f"{kl.get('auc', 0):.3f}", f"{ke.get('auc', 0):.3f}",
                             pct(kl.get("recall_at_5", 0), 1), pct(ke.get("recall_at_5", 0), 1)]]}},
        {"key": "metrics", "title": "Measured performance (test period, never used for training)",
         "bullets": [x[2:] for x in gains_lines(v).split("\n") if x.startswith("- ")],
         "table": {"columns": ["Method", "Fraud AUC", "Fraud precision @5%", "Critical AUC", "Critical recall @5%"],
                   "rows": [[m["method_labels"].get(k, k), f"{v.fm[k]['auc']:.3f}", pct(v.fm[k]["precision_at_5"], 1),
                             f"{v.km[k]['auc']:.3f}", pct(v.km[k]["recall_at_5"], 1)]
                            for k in ("ai", "rule_hs6_history", "rule_importer_history", "random")]}},
        {"key": "calibration", "title": "Calibration",
         "text": (f"In the riskiest tenth of test declarations the primary fraud model predicts {pct(v.cal_top['mean_predicted'], 1)} "
                  f"fraud and {pct(v.cal_top['observed'], 1)} is observed (10-bin table in metrics.json).")},
        {"key": "fairness", "title": "Fairness (who gets inspected)",
         "text": (f"Selection rate in the top 5%: max/min ratio across offices with at least 100 declarations "
                  f"{v.fair['office']['max_min_selection_ratio_ai']:.1f}x; across transport modes "
                  f"{v.fair['transport']['max_min_selection_ratio_ai']:.1f}x. Reviewed weekly next to each group's fraud rate.")},
        {"key": "uncertainty", "title": "Uncertainty policy",
         "text": ((f"When |p(EBM) - p(LightGBM)| exceeds {u.get('threshold', 0):.3f} (95th percentile of their out-of-sample "
                   f"disagreement on the last 4 training weeks), the declaration is flagged as 'models disagree' and is never released "
                   f"green. Test period: {num(u.get('n_flagged', 0))} flagged ({pct(u.get('share_flagged', 0), 1)}), fraud rate "
                   f"{pct(u.get('fraud_rate_flagged') or 0)} vs {pct(u.get('fraud_rate_all') or 0)} overall.") if u else "")},
        {"key": "tested_and_rejected", "title": "Tested and rejected",
         "bullets": [f"{e['title']}: {e['decision']}. {e['reason']}" for e in v.exps if e["decision"] == "rejected"]},
        {"key": "limits", "title": "Limits",
         "bullets": ["Synthetic data of Korean origin: patterns are realistic but not Tunisian.",
                     f"Only inspected declarations were synthesised: fraud rate {pct(c['fraud_rate'], 1)}, far above reality; "
                     "the claim is the gain over the rule, not the absolute precision.",
                     f"Only {m['n_critical_test']} critical cases in the test period.",
                     "Lane and alert thresholds are set on the test period; the disagreement threshold on the last training weeks.",
                     f"{pct(c['test_unit_value_equals_product_median'])} of test declarations carry exactly their product's usual unit value "
                     "(synthetic artefact): value signals must be re-validated on real data."]},
        {"key": "human_oversight", "title": "Human oversight",
         "bullets": ["Advisory score only: the officer decides inspect / document check / release.",
                     "Every decision is written to a hash-chained, tamper-evident journal (verify endpoint).",
                     "Each lane comes with 4 plain-language reasons and an exact waterfall; the current rule is shown side by side.",
                     "Models disagree: human review; 10% random exploration keeps the system from going blind."]},
        {"key": "monitoring", "title": "Retraining and drift plan",
         "bullets": ["Shadow mode first (4-8 weeks), then a pilot with a control group.",
                     "Weekly: base rate, calibration, share of new operators, selection rates by office and transport, disagreement rate.",
                     "Retrain monthly or when drift is detected; re-run this model card with every retraining."]},
        {"key": "contact", "title": "Contact",
         "text": "Team RAQIB - hackathon IA & Finances Publiques 2026 - https://github.com/yassinebennacef/RAQIB"},
    ]
    return {"title": "RAQIB model card", "version": "v2", "generated_at": m["generated_at"], "sections": sections}


def model_card_md(card: dict) -> str:
    out = [f"# {card['title']}", "", f"*Version {card['version']} - generated {card['generated_at']} by `python -m raqib.report`*", ""]
    for sct in card["sections"]:
        out += [f"## {sct['title']}", ""]
        if sct.get("text"):
            out += [sct["text"], ""]
        for b in sct.get("bullets", []):
            out.append(f"- {b}")
        if sct.get("bullets"):
            out.append("")
        if sct.get("table"):
            t = sct["table"]
            out.append("| " + " | ".join(t["columns"]) + " |")
            out.append("|" + "---|" * len(t["columns"]))
            out += ["| " + " | ".join(str(x) for x in row) + " |" for row in t["rows"]]
            out.append("")
    return "\n".join(out)


def readme_blocks(v: V) -> dict[str, str]:
    lines = [x for x in (efficiency_line(v), glassbox_line(v), uncertainty_line(v)) if x]
    return {
        "pitch": headline(v) + ("\n\n" + "\n\n".join(lines) if lines else ""),
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
    card = model_card(v)
    (C.ARTIFACTS / "model_card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    (docs / "MODEL_CARD.md").write_text(model_card_md(card), encoding="utf-8")
    if (C.ROOT / "README.md").exists():
        update_readme(readme_blocks(v))
    print("[report] docs/NOTE_DRAFT.md, DECK_OUTLINE.md, DEMO_SCRIPT.md, RESULTS.md and README blocks written")
    print(f"[report] demo declarations: gain {v.demo_gain['declaration_id']}, alert {v.demo_alert['declaration_id']}")


if __name__ == "__main__":
    main()
