import {
  BrainCircuit,
  ClipboardCheck,
  Database,
  Gauge as GaugeIcon,
  Globe2,
  History,
  ListChecks,
  MessageSquareText,
  Rocket,
  Users,
} from "lucide-react";
import { PageShell } from "@/components/raqib/kit";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, Skeleton } from "@/components/raqib/primitives";
import { TEAM } from "@/content/team";
import { api } from "@/lib/api";
import { num, pct } from "@/lib/format";
import { useApi } from "@/lib/hooks";

export function About() {
  const m = useApi(() => api.metrics(), "metrics");
  const c = useApi(() => api.dataCard(), "datacard");
  const M = m.data;
  const C = c.data;
  const rs = M?.replay_summary;

  const steps = [
    {
      icon: Database,
      title: "Learn from past inspections",
      text: C
        ? `${num(C.train.rows)} inspected declarations (${C.train.period[0]} → ${C.train.period[1]}) with their outcome: fraud or not, critical or not.`
        : "Past inspected declarations with their outcome.",
    },
    {
      icon: History,
      title: "Turn history into risk signals",
      text: "For each product, product family, chapter, importer, declarant, seller, origin and office: smoothed past fraud rate and volume, computed out-of-fold so the model never sees its own answers.",
    },
    {
      icon: BrainCircuit,
      title: "Two calibrated models",
      text: "Duty fraud (revenue): a glass-box Explainable Boosting Machine, as accurate as the black-box LightGBM. Critical fraud (public safety): LightGBM with isotonic calibration. Probabilities, not just scores.",
    },
    {
      icon: GaugeIcon,
      title: "Fill today's capacity",
      text: "Public-safety alerts first, then the highest fraud probabilities, plus an optional 10% random exploration so the system never goes blind. RED / YELLOW / GREEN lanes.",
    },
    {
      icon: MessageSquareText,
      title: "Explain every decision",
      text: "The 4 strongest factors (exact additive contributions), written in plain language with the real historical numbers, next to what the current rule would do.",
    },
    {
      icon: ClipboardCheck,
      title: "The officer decides, the journal records",
      text: "Inspect, document check or release: each decision is appended to a hash-chained journal. Results are measured against the rule on unseen data.",
    },
  ];

  return (
    <PageShell title="About RAQIB" why="Challenge T2 « Ciblage et orientation automatisés des contrôles » — hackathon IA & Finances Publiques.">

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>The problem</CardTitle>
              <CardDescription>Why targeting matters</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-relaxed text-foreground/80">
            <p>
              Customs can physically inspect only a small share of import declarations. Today the choice relies on fixed rules (for example the past fraud
              history of the product) and on officers' experience. Many inspections find nothing, while duty fraud and dangerous goods pass in the green lane.
            </p>
            <p>
              RAQIB (<span className="font-arabic" lang="ar">رقيب</span>, "the overseer") ranks every declaration of the day by two risks — revenue and public
              safety — and fills a fixed inspection capacity with the declarations that matter most, with reasons an officer can check.
            </p>
            {rs ? (
              <p className="rounded-lg border border-ai/30 bg-ai/10 p-3 text-foreground">
                Measured on {num(rs.totals.declarations)} unseen declarations: with the same {num(rs.totals.inspections)} inspections, RAQIB finds{" "}
                <b>{num(rs.policies.ai.frauds)}</b> frauds and <b>{num(rs.policies.ai.threats)}</b> public-safety threats, against{" "}
                <b>{num(rs.policies.rule.frauds)}</b> and <b>{num(rs.policies.rule.threats)}</b> for the current rule and{" "}
                {num(rs.policies.random.frauds)} / {num(rs.policies.random.threats)} at random.
              </p>
            ) : (
              <Skeleton className="h-14" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle className="flex items-center gap-2">
                <Globe2 className="h-4 w-4" /> International precedent
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-2 text-sm leading-relaxed text-foreground/80">
            <p>
              The World Customs Organization's <b>BACUDA</b> project (Korea Customs Service + Institute for Basic Science) built the <b>DATE</b> model (KDD
              2020) and piloted machine-learning targeting with <b>Nigeria Customs</b> in 2020.
            </p>
            <p>
              RAQIB uses the public customs declarations dataset from that same ecosystem (MIT licence) — no Tunisian data, no access to any administration
              system.
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div>
            <CardTitle className="flex items-center gap-2">
              <ListChecks className="h-4 w-4" /> The method in 6 steps
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <ol className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {steps.map((s, i) => (
              <li key={s.title} className="rounded-xl border border-border bg-muted/30 p-4">
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-ai/15 text-ai-light">
                    <s.icon className="h-4 w-4" />
                  </span>
                  <span className="text-xs font-semibold text-muted-foreground">STEP {i + 1}</span>
                </div>
                <div className="mt-2 font-medium text-foreground">{s.title}</div>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{s.text}</p>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <div>
              <CardTitle className="flex items-center gap-2">
                <Rocket className="h-4 w-4" /> Path to production in Tunisia
              </CardTitle>
              <CardDescription>Done by and inside the administration; this prototype never touches its systems</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <ol className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
              {[
                ["Retrain on Tunisian inspection results", "Same recipe, retrained inside the customs information system on past inspected declarations. Training takes minutes on a normal CPU."],
                ["Shadow mode", "RAQIB scores every declaration in parallel with the current rules, without affecting any decision; weekly comparison of hit rates."],
                ["Pilot with a control group", "Some offices or days use RAQIB lanes, others keep the rules: the gain is measured, not assumed. Exploration keeps learning unbiased."],
                ["Weekly drift monitor", "Base rate, calibration, share of new operators and fairness by office and transport, with retraining when they drift."],
              ].map(([t, d], i) => (
                <li key={t} className="rounded-lg border border-border bg-muted/30 p-3">
                  <div className="font-medium text-foreground">
                    {i + 1}. {t}
                  </div>
                  <p className="mt-1 text-muted-foreground">{d}</p>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-4 w-4" /> Team RAQIB
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-2 text-sm">
              {TEAM.map((t, i) => (
                <li key={i} className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2">
                  <span className="text-foreground">{t.name || "Team member"}</span>
                  <span className="text-xs text-muted-foreground">{t.role}</span>
                </li>
              ))}
            </ul>
            {C && (
              <p className="mt-3 text-xs text-muted-foreground">
                Data: {C.dataset} ({C.licence}); HS names: datasets/harmonized-system ({C.hs_names.licence}). Fraud rate in the data {pct(C.fraud_rate, 1)}.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </PageShell>
  );
}
