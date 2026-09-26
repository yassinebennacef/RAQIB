import { AlertTriangle, CheckCircle2, Database, Scale } from "lucide-react";
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { PageShell } from "@/components/raqib/kit";
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  ErrorState,
  InfoTip,
  Segmented,
  Skeleton,
} from "@/components/raqib/primitives";
import { api, type MethodKey, type TargetKey } from "@/lib/api";
import { dec, num, pct } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { COLORS } from "@/lib/colors";

const METHODS: MethodKey[] = ["ai", "rule_hs6_history", "rule_importer_history", "random"];
const METHOD_COLOR: Record<MethodKey, string> = {
  ai: COLORS.ai,
  rule_hs6_history: COLORS.rule,
  rule_importer_history: "#b45309",
  random: COLORS.random,
};
const tooltipStyle = { background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 };

export function ModelLab() {
  const m = useApi(() => api.metrics(), "metrics");
  const card = useApi(() => api.dataCard(), "datacard");
  const [target, setTarget] = useState<TargetKey>("fraud");
  const [fairKey, setFairKey] = useState<"office" | "transport">("office");

  if (m.error && !m.data) return <ErrorState message={m.error} onRetry={m.reload} />;
  if (!m.data || !card.data) {
    return (
      <div className="grid grid-cols-2 gap-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-64" />
        ))}
      </div>
    );
  }
  const M = m.data;
  const C = card.data;
  const T = M.targets[target];
  const main = target === "fraud" ? "precision" : "recall";
  const cols: { key: keyof (typeof T.methods)["ai"]; label: string }[] = [
    { key: "auc", label: "AUC" },
    { key: "precision_at_1", label: "Precision @1%" },
    { key: "precision_at_5", label: "Precision @5%" },
    { key: "precision_at_10", label: "Precision @10%" },
    { key: "recall_at_1", label: "Recall @1%" },
    { key: "recall_at_5", label: "Recall @5%" },
    { key: "recall_at_10", label: "Recall @10%" },
  ];
  const best = Object.fromEntries(cols.map((c) => [c.key, Math.max(...METHODS.map((k) => T.methods[k][c.key] as number))]));

  const headline = [
    {
      label: "Duty fraud · precision @5%",
      ai: M.targets.fraud.methods.ai.precision_at_5,
      rule: M.targets.fraud.methods.rule_hs6_history.precision_at_5,
      rnd: M.targets.fraud.methods.random.precision_at_5,
      g: M.targets.fraud.gain_vs_rule,
      tip: "Share of the top 5% riskiest test declarations that were really fraudulent.",
    },
    {
      label: "Public safety · recall @5%",
      ai: M.targets.critical.methods.ai.recall_at_5,
      rule: M.targets.critical.methods.rule_hs6_history.recall_at_5,
      rnd: M.targets.critical.methods.random.recall_at_5,
      g: M.targets.critical.gain_vs_rule,
      tip: "Share of all critical (public-safety) cases of the test period caught by inspecting the top 5%.",
    },
  ];

  const barData = METHODS.map((k) => ({
    method: M.method_labels[k].replace("Rule: ", "").replace(" selection", ""),
    key: k,
    fraud: M.targets.fraud.methods[k].precision_at_5,
    critical: M.targets.critical.methods[k].recall_at_5,
  }));
  const weekly = T.weekly.map((w) => ({
    week: w.start.slice(5),
    ai: main === "precision" ? w.precision_ai : w.recall_ai,
    rule: main === "precision" ? w.precision_rule : w.recall_rule,
    base: w.base_rate,
    positives: w.positives,
  }));
  const calib = T.calibration.map((c) => ({ x: c.mean_predicted, y: c.observed, n: c.n }));
  const calMax = Math.max(...calib.map((c) => Math.max(c.x, c.y)), 0.05);
  const fair = M.fairness[fairKey].rows.map((r) => ({
    label: r.label.length > 26 ? `${r.label.slice(0, 25)}…` : r.label,
    ai: r.selection_rate_ai,
    rule: r.selection_rate_rule,
    fraud: r.fraud_rate,
    n: r.n,
  }));
  const groups = T.importance.groups.map((g) => ({ label: g.label, share: g.share }));
  const valueShare = M.targets.fraud.importance.groups.find((g) => g.group === "value")?.share ?? 0;
  const critR5 = M.targets.critical.methods.ai.recall_at_5;
  const critSe = M.targets.critical.methods.ai.recall_se_at_5;
  const RS = M.replay_summary;

  return (
    <PageShell
        title="Model lab"
        why={`Measured results on ${num(M.recipe.n_test)} declarations the models never saw (${M.recipe.test[0]} → ${M.recipe.test[1]}), against today's rules.`} actions={<>
        <Segmented
          value={target}
          onChange={setTarget}
          options={[
            { value: "fraud", label: "Duty fraud (revenue)" },
            { value: "critical", label: "Critical fraud (public safety)" },
          ]}
        />
      </>}>

      {/* Headline */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {headline.map((h) => (
          <Card key={h.label} className="px-5 py-4">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              {h.label} <InfoTip text={h.tip} />
            </div>
            <div className="mt-2 flex flex-wrap items-end gap-6">
              <div>
                <div className="text-4xl font-bold tabular text-ai-light">{pct(h.ai)}</div>
                <div className="text-xs text-muted-foreground">RAQIB AI</div>
              </div>
              <div>
                <div className="text-3xl font-semibold tabular" style={{ color: COLORS.rule }}>
                  {pct(h.rule)}
                </div>
                <div className="text-xs text-muted-foreground">best rule (product history)</div>
              </div>
              <div>
                <div className="text-2xl font-semibold tabular text-muted-foreground">{pct(h.rnd)}</div>
                <div className="text-xs text-muted-foreground">random</div>
              </div>
              <div className="ml-auto rounded-lg border border-ai/40 bg-ai/10 px-3 py-2 text-right">
                <div className="text-lg font-semibold tabular text-ai-light">
                  +{(h.g.mean_gain * 100).toFixed(1)} pts
                </div>
                <div className="text-[11px] text-muted-foreground">
                  95% CI [{(h.g.ci95[0] * 100).toFixed(1)}, {(h.g.ci95[1] * 100).toFixed(1)}] · bootstrap ×{h.g.n_boot}
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Table */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>{T.label}: AI vs current practice</CardTitle>
            <CardDescription>
              Test base rate {pct(T.base_rate, 1)} · {num(T.n_positive)} positive cases · top-k with k = ceil(share × {num(M.recipe.n_test)})
            </CardDescription>
          </div>
          <InfoTip text="Precision @k% = share of the k% highest-scored declarations that are positive. Recall @k% = share of all positive cases found in that top k%. AUC = ranking quality over all thresholds (0.5 = random)." />
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-4 font-medium">Method</th>
                {cols.map((c) => (
                  <th key={c.key} className="py-2 pr-4 text-right font-medium">
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {METHODS.map((k) => (
                <tr key={k} className={cn("border-b border-border/60", k === "ai" && "bg-ai/5")}>
                  <td className="py-2 pr-4">
                    <span className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: METHOD_COLOR[k] }} />
                      <span className={k === "ai" ? "font-semibold text-foreground" : "text-foreground/80"}>{M.method_labels[k]}</span>
                    </span>
                  </td>
                  {cols.map((c) => {
                    const v = T.methods[k][c.key] as number;
                    return (
                      <td
                        key={c.key}
                        className={cn("py-2 pr-4 text-right tabular", v === best[c.key] ? "font-semibold text-ai-light" : "text-foreground/80")}
                      >
                        {c.key === "auc" ? dec(v, 3) : pct(v, 1)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          {target === "critical" && (
            <p className="mt-2 text-xs text-lane-yellow">
              Small sample: {M.n_critical_test} critical cases in the test period → recall @5% = {pct(critR5)} ± {(critSe * 100).toFixed(0)} points (1 standard error).
            </p>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {/* Bars */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>At 5% inspection capacity</CardTitle>
              <CardDescription>Solid bars: duty-fraud precision @5% · faded bars: public-safety recall @5%</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="method" tick={{ fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#334155" }} />
                <YAxis tickFormatter={(v) => pct(v)} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} domain={[0, 1]} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => pct(Number(v), 1)} />
                <Bar dataKey="fraud" name="Duty fraud precision @5%" radius={[4, 4, 0, 0]}>
                  {barData.map((b) => (
                    <Cell key={b.key} fill={METHOD_COLOR[b.key]} />
                  ))}
                </Bar>
                <Bar dataKey="critical" name="Public-safety recall @5%" radius={[4, 4, 0, 0]} fillOpacity={0.55}>
                  {barData.map((b) => (
                    <Cell key={b.key} fill={METHOD_COLOR[b.key]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Weekly */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Week by week stability</CardTitle>
              <CardDescription>
                {main === "precision" ? "Precision" : "Recall"} @5% within each week of the test period
                {target === "critical" && " (few cases per week: noisy)"}
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={weekly} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="week" tick={{ fontSize: 11 }} tickLine={false} axisLine={{ stroke: "#334155" }} />
                <YAxis tickFormatter={(v) => pct(v)} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} domain={[0, 1]} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => (v == null ? "—" : pct(Number(v), 1))} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line dataKey="ai" name="RAQIB AI" stroke={COLORS.ai} strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
                <Line dataKey="rule" name="Rule (product history)" stroke={COLORS.rule} strokeWidth={2} dot={{ r: 3 }} connectNulls />
                {main === "precision" && (
                  <Line dataKey="base" name="Base rate (random)" stroke={COLORS.random} strokeDasharray="4 4" strokeWidth={1.5} dot={false} />
                )}
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Calibration */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Calibration</CardTitle>
              <CardDescription>Predicted probability vs observed rate, 10 equal-size groups of test declarations</CardDescription>
            </div>
            <InfoTip text="Points close to the diagonal mean that a declaration shown at 60% risk is fraudulent about 60% of the time. Isotonic calibration fitted on out-of-fold training predictions." />
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 8, right: 16, left: -12, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" dataKey="x" name="Predicted" domain={[0, calMax]} tickFormatter={(v) => pct(v)} tick={{ fontSize: 11 }} />
                <YAxis type="number" dataKey="y" name="Observed" domain={[0, calMax]} tickFormatter={(v) => pct(v)} tick={{ fontSize: 11 }} />
                <ZAxis type="number" dataKey="n" range={[60, 60]} />
                <ReferenceLine segment={[{ x: 0, y: 0 }, { x: calMax, y: calMax }]} stroke="#475569" strokeDasharray="4 4" />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => pct(Number(v), 1)} />
                <Scatter data={calib} fill={COLORS.ai} line={{ stroke: COLORS.ai, strokeWidth: 2 }} />
              </ScatterChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Importance */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>What the model relies on</CardTitle>
              <CardDescription>Share of the primary model's importance, grouped by concept</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={groups} layout="vertical" margin={{ top: 0, right: 16, left: 40, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" tickFormatter={(v) => pct(v)} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} width={130} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => pct(Number(v), 1)} />
                <Bar dataKey="share" name="Share of gain" fill={COLORS.ai} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Fairness */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle className="flex items-center gap-2">
              <Scale className="h-4 w-4" /> Who gets inspected? (fairness view)
            </CardTitle>
            <CardDescription>
              Selection rate in the top 5% ({num(M.fairness.k)} inspections) by {fairKey === "office" ? "customs office" : "mode of transport"}, AI vs rule, next to the
              actual fraud rate of each group
              {M.fairness[fairKey].max_min_selection_ratio_ai != null &&
                ` · max/min AI selection ratio (groups ≥ 100 declarations): ${dec(M.fairness[fairKey].max_min_selection_ratio_ai, 1)}×`}
            </CardDescription>
          </div>
          <Segmented
            value={fairKey}
            onChange={setFairKey}
            options={[
              { value: "office", label: "Office" },
              { value: "transport", label: "Transport" },
            ]}
          />
        </CardHeader>
        <CardContent className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={fair} margin={{ top: 8, right: 8, left: -8, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
              <YAxis tickFormatter={(v) => pct(v)} tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={tooltipStyle} formatter={(v) => pct(Number(v), 1)} />
              <Legend wrapperStyle={{ fontSize: 12 }} verticalAlign="top" />
              <Bar dataKey="ai" name="AI selection rate" fill={COLORS.ai} radius={[3, 3, 0, 0]} />
              <Bar dataKey="rule" name="Rule selection rate" fill={COLORS.rule} radius={[3, 3, 0, 0]} />
              <Bar dataKey="fraud" name="Actual fraud rate" fill="#475569" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {/* Replay summary */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Daily replay at {pct(RS.rate)} capacity</CardTitle>
              <CardDescription>
                {num(RS.totals.inspections)} inspections over {RS.n_days} days for every policy · the test period holds {num(RS.totals.frauds)} frauds and{" "}
                {num(RS.totals.threats)} threats
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="py-2 font-medium">Policy</th>
                  <th className="py-2 text-right font-medium">Frauds</th>
                  <th className="py-2 text-right font-medium">Threats</th>
                  <th className="py-2 text-right font-medium">Hit rate</th>
                  <th className="py-2 text-right font-medium">Products inspected</th>
                </tr>
              </thead>
              <tbody>
                {(["ai", "ai_explore", "rule", "random"] as const).map((k) => {
                  const p = RS.policies[k];
                  return (
                    <tr key={k} className="border-b border-border/60">
                      <td className="py-2 text-foreground">{p.label}</td>
                      <td className="py-2 text-right tabular text-foreground">{num(p.frauds)}</td>
                      <td className="py-2 text-right tabular text-foreground">{num(p.threats)}</td>
                      <td className="py-2 text-right tabular text-foreground/80">{pct(p.hit_rate, 1)}</td>
                      <td className="py-2 text-right tabular text-foreground/80">{num(p.distinct_hs6)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-muted-foreground">
              Exploration ({pct(RS.explore)} of slots at random) costs {num(RS.policies.ai.frauds - RS.policies.ai_explore.frauds)} frauds but widens coverage to{" "}
              {num(RS.policies.ai_explore.distinct_hs6)} distinct products (vs {num(RS.policies.ai.distinct_hs6)}), so the model keeps learning.
            </p>
          </CardContent>
        </Card>

        {/* Limits */}
        <Card>
          <CardHeader>
            <div>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-4 w-4" /> Data & honest limits
              </CardTitle>
              <CardDescription>What these numbers do and do not show</CardDescription>
            </div>
            <Badge>{C.licence} · {num(C.rows)} rows</Badge>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-2.5 text-sm text-foreground/80">
              <li className="flex gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-lane-green" />
                <span>
                  Public synthetic data of Korean origin (CTGAN, Korea Customs Service & IBS): {num(C.unique.importers)} importers,{" "}
                  {num(C.unique.hs6)} products, {num(C.unique.origins)} origins. Realistic patterns, not Tunisian data.
                </span>
              </li>
              <li className="flex gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-lane-yellow" />
                <span>
                  Only inspected declarations were synthesised, so the fraud rate is {pct(C.fraud_rate, 1)} — far above reality. Absolute precision is
                  optimistic; what we claim is the gain over the rule on the same data.
                </span>
              </li>
              <li className="flex gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-lane-yellow" />
                <span>
                  {M.n_critical_test} critical cases in the test period: public-safety recall @5% is {pct(critR5)} ± {(critSe * 100).toFixed(0)} points (1 s.e.).
                </span>
              </li>
              <li className="flex gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-lane-yellow" />
                <span>
                  Value and mass matter here ({pct(valueShare)} of the fraud model's importance): without them, LightGBM duty-fraud precision @5% falls from{" "}
                  {pct(M.ablation_no_value.fraud.full_precision_at_5)} to {pct(M.ablation_no_value.fraud.precision_at_5)} and public-safety recall @5% from{" "}
                  {pct(M.ablation_no_value.critical.full_recall_at_5)} to {pct(M.ablation_no_value.critical.recall_at_5)}. But {pct(C.test_unit_value_equals_product_median)} of test declarations
                  carry exactly their product's usual unit value (a synthetic-data artefact), so value signals must be re-validated on real data.
                </span>
              </li>
              <li className="flex gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-lane-yellow" />
                <span>
                  {pct(C.test_new_operators.importer)} of test declarations come from importers never seen in training; they are treated as average risk.
                  Alert and lane thresholds are set on the test period; in production they come from the previous weeks.
                </span>
              </li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </PageShell>
  );
}
