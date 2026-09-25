import { motion } from "framer-motion";
import { ArrowLeft, Eye, FileSearch, Gavel, Hash, ShieldAlert, ShieldCheck, UserRound } from "lucide-react";
import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { NetworkGraph } from "@/components/NetworkGraph";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  ErrorState,
  InfoTip,
  Skeleton,
} from "@/components/ui/primitives";
import { Gauge, LaneBadge, ReasonList } from "@/components/visuals";
import { api, type DecisionEntry, type OperatorHistory } from "@/lib/api";
import { compact, num, pct, pctile, shortHash } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { LANE_META } from "@/lib/lanes";
import { cn, COLORS } from "@/lib/utils";

function readOfficer() {
  try {
    return window.localStorage.getItem("raqib-officer") || "Officer A";
  } catch {
    return "Officer A";
  }
}

const inputCls =
  "h-9 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100 outline-none placeholder:text-slate-600 focus:border-ai";

export default function Inspector() {
  const { id = "" } = useParams();
  const [sp] = useSearchParams();
  const rate = Number(sp.get("rate") ?? 0.05) || 0.05;
  const explore = Number(sp.get("explore") ?? 0) || 0;
  const q = useApi(() => api.declaration(id, rate, explore), `decl-${id}-${rate}-${explore}`);
  const [reveal, setReveal] = useState(false);
  const [officer, setOfficer] = useState(readOfficer);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [logged, setLogged] = useState<DecisionEntry[]>([]);

  if (q.error && !q.data) return <ErrorState message={q.error} onRetry={q.reload} />;
  if (!q.data) {
    return (
      <div className="grid grid-cols-12 gap-4">
        <Skeleton className="col-span-12 h-16" />
        <Skeleton className="col-span-5 h-80" />
        <Skeleton className="col-span-7 h-80" />
      </div>
    );
  }
  const { declaration: dc, ai, rule, day, truth, history, network } = q.data;
  const decisions = [...logged, ...q.data.decisions.slice().reverse()];
  const agree = (ai.lane === "RED") === rule.selected;

  async function decide(decision: DecisionEntry["decision"]) {
    setBusy(true);
    try {
      try {
        window.localStorage.setItem("raqib-officer", officer);
      } catch {
        /* storage unavailable */
      }
      const res = await api.decide({ declaration_id: id, decision, comment, officer });
      toast.success(`Decision logged: ${decision.replace("_", " ")}`, {
        description: `Journal entry #${res.id} · hash ${shortHash(res.hash)}…`,
      });
      setLogged((l) => [
        { id: res.id, ts: res.ts, declaration_id: id, decision, comment, officer, ai: {}, prev_hash: res.prev_hash, hash: res.hash },
        ...l,
      ]);
      setComment("");
    } catch (e) {
      toast.error("Could not log the decision", { description: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/" className="mb-1 inline-flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200">
            <ArrowLeft className="h-3.5 w-3.5" /> Control room
          </Link>
          <h1 className="flex flex-wrap items-center gap-3 text-xl font-semibold tracking-tight text-slate-50">
            Declaration <span className="font-mono">{dc.id}</span>
            <LaneBadge lane={ai.lane} alert={ai.alert} size="lg" />
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-400">
            <span className="font-mono text-slate-300">{dc.hs6}</span> · {dc.hs_desc}
          </p>
          <p className="mt-0.5 text-xs text-slate-500">
            {dc.date} · {dc.office_label} · {dc.transport_label} · origin {dc.origin} · value {compact(dc.item_price)} KRW ·{" "}
            {num(dc.net_mass)} kg · tax {dc.tax_rate}%
          </p>
        </div>
        <Badge className="border-slate-700 py-1 text-slate-300">
          <Gavel className="h-3.5 w-3.5" /> Advisory score — the officer decides
        </Badge>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        {/* Left: risk + decision */}
        <div className="flex flex-col gap-4 xl:col-span-5">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Risk assessment</CardTitle>
                <CardDescription>{ai.lane_reason}</CardDescription>
              </div>
              <InfoTip text="Calibrated probabilities from two LightGBM models trained on 15 months of past inspections, ranked against the other declarations of the same day." />
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2">
                <Gauge
                  value={ai.p_fraud}
                  label="Duty fraud"
                  sub={`higher than ${pctile(ai.fraud_percentile)}% of declarations`}
                  color={ai.p_fraud >= 0.5 ? COLORS.red : ai.p_fraud >= 0.3 ? COLORS.yellow : COLORS.ai}
                />
                <Gauge
                  value={ai.p_critical}
                  label="Public-safety threat"
                  sub={`higher than ${pctile(ai.critical_percentile)}% of declarations`}
                  color={ai.alert ? COLORS.red : COLORS.aiLight}
                />
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
                <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-2">
                  <div className="text-slate-500">AI rank today</div>
                  <div className="text-base font-semibold tabular text-slate-100">
                    {ai.rank_in_day} <span className="text-xs text-slate-500">/ {day.n}</span>
                  </div>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-2">
                  <div className="text-slate-500">Capacity today</div>
                  <div className="text-base font-semibold tabular text-slate-100">{day.capacity} inspections</div>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-2">
                  <div className="text-slate-500">Safety alert</div>
                  <div className={cn("text-base font-semibold", ai.alert ? "text-lane-red" : "text-slate-300")}>{ai.alert ? "Yes" : "No"}</div>
                </div>
              </div>

              <div className="mt-4 text-[11px] font-semibold uppercase tracking-wider text-slate-400">AI vs what the current rule would do</div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                <div className="rounded-lg border p-3" style={{ borderColor: `${COLORS.ai}55`, background: `${COLORS.ai}10` }}>
                  <div className="text-xs text-ai-light">RAQIB AI</div>
                  <div className="mt-1 text-sm font-semibold" style={{ color: LANE_META[ai.lane].color }}>
                    {ai.alert && ai.lane === "RED" ? "Inspect · safety alert" : LANE_META[ai.lane].action}
                  </div>
                  <div className="mt-1 text-[11px] text-slate-400">
                    rank {ai.rank_in_day} of {day.n} by risk
                  </div>
                </div>
                <div className="rounded-lg border p-3" style={{ borderColor: `${COLORS.rule}55`, background: `${COLORS.rule}10` }}>
                  <div className="text-xs" style={{ color: COLORS.rule }}>
                    Current rule · product history
                  </div>
                  <div className="mt-1 text-sm font-semibold text-slate-100">{rule.decision === "INSPECT" ? "Inspect" : "Release"}</div>
                  <div className="mt-1 text-[11px] text-slate-400">
                    product:{" "}
                    {rule.hs6_past_fraud_rate == null
                      ? "no history"
                      : `${pct(rule.hs6_past_fraud_rate)} fraud on ${num(rule.hs6_past_declarations)} past`}
                  </div>
                </div>
              </div>
              <p className="mt-2 text-[11px] text-slate-500">
                {agree ? "AI and rule agree on inspection for this one. " : "AI and rule disagree here: this is where the measured gain comes from. "}
                {rule.explanation}
              </p>
            </CardContent>
          </Card>

          {/* Decision */}
          <Card>
            <CardHeader>
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Gavel className="h-4 w-4" /> Officer decision
                </CardTitle>
                <CardDescription>The AI advises; the officer decides. Each decision goes to a hash-chained journal.</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="grid grid-cols-3 gap-2">
                <label className="flex flex-col gap-1 text-xs text-slate-400">
                  Officer
                  <input value={officer} onChange={(e) => setOfficer(e.target.value)} className={inputCls} />
                </label>
                <label className="col-span-2 flex flex-col gap-1 text-xs text-slate-400">
                  Comment
                  <input
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="e.g. check invoice vs declared value"
                    className={inputCls}
                  />
                </label>
              </div>
              <div className="grid grid-cols-3 gap-2">
                <Button variant="red" disabled={busy} onClick={() => decide("INSPECT")}>
                  <ShieldAlert className="h-4 w-4" /> Inspect
                </Button>
                <Button variant="yellow" disabled={busy} onClick={() => decide("DOCUMENT_CHECK")}>
                  <FileSearch className="h-4 w-4" /> Document check
                </Button>
                <Button variant="green" disabled={busy} onClick={() => decide("RELEASE")}>
                  <ShieldCheck className="h-4 w-4" /> Release
                </Button>
              </div>
              {decisions.length > 0 && (
                <ul className="thin-scroll flex max-h-36 flex-col gap-1.5 overflow-y-auto">
                  {decisions.map((e) => (
                    <li
                      key={`${e.id}-${e.hash}`}
                      className="flex items-center justify-between gap-2 rounded-md border border-slate-800 bg-slate-950/50 px-2.5 py-1.5 text-xs"
                    >
                      <span className="flex min-w-0 items-center gap-2">
                        <UserRound className="h-3.5 w-3.5 shrink-0 text-slate-500" />
                        <span className="text-slate-200">{e.officer}</span>
                        <span className="font-semibold text-slate-100">{e.decision.replace("_", " ")}</span>
                        {e.comment && <span className="truncate text-slate-500">“{e.comment}”</span>}
                      </span>
                      <span className="flex shrink-0 items-center gap-1 font-mono text-[10px] text-slate-500" title={e.hash}>
                        <Hash className="h-3 w-3" />
                        {shortHash(e.hash)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="flex items-center justify-between gap-3 border-t border-slate-800 pt-3">
                <span className="text-[11px] text-slate-500">Demo only: the real outcome is known after inspection.</span>
                <Button variant="outline" size="sm" onClick={() => setReveal((r) => !r)}>
                  <Eye className="h-4 w-4" /> {reveal ? "Hide" : "Reveal"} outcome
                </Button>
              </div>
              {reveal && (
                <motion.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn(
                    "rounded-lg border p-3 text-sm",
                    truth.fraud ? "border-lane-red/40 bg-lane-red/10 text-slate-100" : "border-lane-green/40 bg-lane-green/10 text-slate-100",
                  )}
                >
                  <span className="font-semibold">Inspection outcome: </span>
                  {truth.fraud ? "fraud found" : "no fraud"}
                  {truth.critical ? " · critical violation (public safety)" : ""}
                </motion.div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right: reasons */}
        <div className="flex flex-col gap-4 xl:col-span-7">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Why this risk — duty fraud</CardTitle>
                <CardDescription>The 4 strongest factors (exact TreeSHAP contributions of the model), with the real historical numbers</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <ReasonList reasons={ai.reasons_fraud} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <div>
                <CardTitle className="flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-lane-red" /> Public-safety signals
                </CardTitle>
                <CardDescription>Top 2 factors of the critical-fraud model</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <ReasonList reasons={ai.reasons_critical} compact />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Operators + record | network */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <div className="flex flex-col gap-3 xl:col-span-5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <OperatorCard h={history.importer} avg={history.average_fraud_rate} />
            <OperatorCard h={history.declarant} avg={history.average_fraud_rate} />
            <OperatorCard h={history.seller} avg={history.average_fraud_rate} />
          </div>
          <Card className="flex-1">
            <CardHeader>
              <CardTitle>Declaration record</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs sm:grid-cols-3">
                {(
                  [
                    ["Declaration ID", dc.id],
                    ["Date", dc.date],
                    ["HS6", dc.hs6],
                    ["Origin / departure", `${dc.origin} / ${dc.departure}`],
                    ["Office", dc.office_label],
                    ["Transport", dc.transport_label],
                    ["Importer", dc.importer],
                    ["Declarant", dc.declarant],
                    ["Seller", dc.seller ?? "not declared"],
                    ["Courier", dc.courier ?? "—"],
                    ["Process type", dc.process_type],
                    ["Import type / use", `${dc.import_type} / ${dc.import_use}`],
                    ["Payment type", String(dc.payment_type)],
                    ["Tax type / rate", `${dc.tax_type} / ${dc.tax_rate}%`],
                    ["Net mass", `${num(dc.net_mass)} kg`],
                    ["Item price", `${num(dc.item_price)} KRW`],
                    ["Unit value", `${compact(dc.unit_value)} KRW/kg`],
                    ["Origin indicator", dc.origin_indicator],
                  ] as [string, string][]
                ).map(([k, v]) => (
                  <div key={k} className="min-w-0">
                    <dt className="text-slate-500">{k}</dt>
                    <dd className="truncate font-mono text-slate-200" title={v}>
                      {v}
                    </dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
        </div>
        <Card className="xl:col-span-7">
          <CardHeader>
            <div>
              <CardTitle>Operator network</CardTitle>
              <CardDescription>
                {dc.seller
                  ? "This declarant's other importers (left) and this seller's other importers (right), with their past fraud rates"
                  : "This declarant's other importers, with their past fraud rates (seller not declared)"}
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <NetworkGraph nodes={network.nodes} links={network.links} avg={history.average_fraud_rate} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function OperatorCard({ h, avg }: { h: OperatorHistory; avg: number }) {
  const rate = h.fraud_rate;
  const color = rate == null ? "#64748b" : rate >= 0.4 ? COLORS.red : rate >= 0.2 ? COLORS.yellow : COLORS.green;
  return (
    <Card className="px-4 py-3">
      <div className="flex items-center justify-between gap-2">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">{h.role}</div>
        {h.missing ? (
          <Badge className="border-slate-600">not declared</Badge>
        ) : h.is_new ? (
          <Badge className="border-slate-600">new</Badge>
        ) : h.thin_history ? (
          <Badge className="border-lane-yellow/40 text-lane-yellow">thin</Badge>
        ) : null}
      </div>
      <div className="mt-1 truncate font-mono text-sm text-slate-100">{h.id ?? "—"}</div>
      <div className="mt-1 text-2xl font-semibold tabular" style={{ color }}>
        {rate == null ? "—" : pct(rate)}
      </div>
      <div className="text-[11px] leading-snug text-slate-500">
        {h.missing
          ? "treated as average risk"
          : h.is_new
            ? "no past declarations"
            : `fraud on ${num(h.past_declarations)} past decl. (avg ${pct(avg)})`}
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
        <div className="h-full rounded-full" style={{ width: `${Math.min(100, (rate ?? 0) * 100)}%`, background: color }} />
      </div>
    </Card>
  );
}
