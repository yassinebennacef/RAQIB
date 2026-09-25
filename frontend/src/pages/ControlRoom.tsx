import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Check, FastForward, Pause, Play, RotateCcw, Shuffle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PageTitle } from "@/components/Layout";
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
  Segmented,
  Skeleton,
  Slider,
  Stat,
  Switch,
} from "@/components/ui/primitives";
import { AnimatedNumber, Dot, LaneBadge } from "@/components/visuals";
import { LANE_META } from "@/lib/lanes";
import { api, type PolicyKey, type StreamItem } from "@/lib/api";
import { compact, num, pct, truncate } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { cn, COLORS } from "@/lib/utils";

const LANE_ORDER = { RED: 0, YELLOW: 1, GREEN: 2 } as const;
const FEED_MAX = 40;

function cumsum(a: number[] | undefined): number[] {
  const out: number[] = [];
  let s = 0;
  for (const v of a ?? []) {
    s += v;
    out.push(s);
  }
  return out;
}

export default function ControlRoom() {
  const navigate = useNavigate();
  const [capPct, setCapPct] = useState(5);
  const [explore, setExplore] = useState(false);
  const [speed, setSpeed] = useState(3);
  const [playing, setPlaying] = useState(false);
  const [day, setDay] = useState(-1);
  const [metric, setMetric] = useState<"frauds" | "threats">("frauds");

  const rate = capPct / 100;
  const exp = explore ? 0.1 : 0;
  const replay = useApi(() => api.replay(rate, exp), `replay-${rate}-${exp}`);
  const R = replay.data;
  const nDays = R?.n_days ?? 91;
  const started = day >= 0;
  const d = Math.max(day, 0);
  const stream = useApi(() => api.stream(d, rate, exp), `stream-${d}-${rate}-${exp}`);

  // playback clock
  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => setDay((x) => Math.min(x + 1, nDays - 1)), 1000 / speed);
    return () => window.clearInterval(id);
  }, [playing, speed, nDays]);
  useEffect(() => {
    if (playing && day >= nDays - 1) setPlaying(false);
  }, [playing, day, nDays]);

  // space bar = play / pause
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (e.code === "Space" && tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "BUTTON") {
        e.preventDefault();
        setPlaying((p) => !p);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const aiKey: PolicyKey = explore ? "ai_explore" : "ai";
  const cum = useMemo(
    () => ({
      n: cumsum(R?.n),
      frauds: cumsum(R?.day_frauds),
      threats: cumsum(R?.day_threats),
      green: cumsum(R?.policies[aiKey]?.green),
    }),
    [R, aiKey],
  );
  const at = (arr: number[] | undefined) => (started && arr ? (arr[d] ?? 0) : 0);
  const ai = R?.policies[aiKey];
  const rule = R?.policies.rule;
  const rnd = R?.policies.random;
  const aiF = at(ai?.cum_frauds);
  const ruleF = at(rule?.cum_frauds);
  const rndF = at(rnd?.cum_frauds);
  const aiT = at(ai?.cum_threats);
  const ruleT = at(rule?.cum_threats);
  const rndT = at(rnd?.cum_threats);
  const insp = at(ai?.cum_inspected);
  const declSoFar = at(cum.n);
  const threatsSoFar = at(cum.threats);
  const greenSoFar = at(cum.green);
  const gain = aiF - ruleF;

  const cumKey = metric === "frauds" ? "cum_frauds" : "cum_threats";
  const chartData = useMemo(() => {
    if (!R) return [];
    return R.dates.map((date, i) => ({
      date: date.slice(5),
      ai: i <= day ? R.policies[aiKey][cumKey][i] : null,
      rule: i <= day ? R.policies.rule[cumKey][i] : null,
      random: i <= day ? R.policies.random[cumKey][i] : null,
    }));
  }, [R, day, aiKey, cumKey]);
  const yMax = R
    ? Math.max(...(["ai", "ai_explore", "rule", "random"] as PolicyKey[]).map((k) => R.policies[k][cumKey].at(-1) ?? 0), 1)
    : 10;

  const items = useMemo(
    () =>
      (stream.data?.items ?? [])
        .slice()
        .sort((a, b) => LANE_ORDER[a.lane] - LANE_ORDER[b.lane] || a.rank_in_day - b.rank_in_day),
    [stream.data],
  );
  const counts = useMemo(() => {
    const c = { RED: 0, YELLOW: 0, GREEN: 0 };
    for (const it of items) c[it.lane] += 1;
    return c;
  }, [items]);

  const open = (id: string) => navigate(`/declaration/${id}?rate=${rate}&explore=${exp}`);
  const reset = () => {
    setPlaying(false);
    setDay(-1);
  };

  if (replay.error && !R) return <ErrorState message={replay.error} onRetry={replay.reload} />;

  return (
    <div className="flex flex-col gap-4">
      <PageTitle
        title="Control room"
        why="Replay of 91 real test days: with the SAME daily inspection capacity, who catches more fraud and more public-safety threats?"
      >
        <Badge className="border-ai/40 text-ai-light">Test period Apr–Jun 2021 · never seen in training</Badge>
      </PageTitle>

      {/* Controls */}
      <Card className="flex flex-wrap items-center gap-x-8 gap-y-3 px-5 py-3">
        <div className="flex min-w-[260px] flex-1 items-center gap-3">
          <div className="w-32 shrink-0">
            <div className="flex items-center gap-1 text-xs font-medium text-slate-300">
              Inspection capacity
              <InfoTip text="Share of each day's declarations that can be physically inspected. Every policy (AI, rule, random) gets exactly the same number of inspections." />
            </div>
            <div className="text-lg font-semibold tabular text-slate-50">{capPct}% / day</div>
          </div>
          <Slider value={capPct} min={1} max={20} onChange={(v) => setCapPct(v)} label="Inspection capacity" />
        </div>
        <div className="flex items-center gap-3">
          <Switch checked={explore} onChange={setExplore} label="Exploration" />
          <div>
            <div className="flex items-center gap-1 text-xs font-medium text-slate-300">
              <Shuffle className="h-3.5 w-3.5" /> Exploration 10%
              <InfoTip text="A small random share of the capacity is inspected at random, so the system keeps learning about products and operators it would never pick (it never goes blind)." />
            </div>
            <div className="text-[11px] text-slate-500">{explore ? "on: 10% of slots random" : "off"}</div>
          </div>
        </div>
        <div className="flex w-56 items-center gap-3">
          <div className="w-20 shrink-0 text-xs text-slate-300">
            Speed
            <div className="text-sm font-semibold tabular text-slate-100">{speed} days/s</div>
          </div>
          <Slider value={speed} min={1} max={8} onChange={setSpeed} label="Replay speed" />
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={() => setPlaying((p) => !p)} disabled={!R || day >= nDays - 1} className="w-28">
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            {playing ? "Pause" : started ? "Resume" : "Play"}
          </Button>
          <Button variant="outline" size="icon" onClick={reset} aria-label="Reset" title="Reset">
            <RotateCcw className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => {
              setPlaying(false);
              setDay(nDays - 1);
            }}
            aria-label="Skip to the end"
            title="Skip to the end"
          >
            <FastForward className="h-4 w-4" />
          </Button>
        </div>
      </Card>

      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        <Stat
          label="Day"
          value={
            <span>
              {started ? d + 1 : 0}
              <span className="text-base text-slate-500"> / {nDays}</span>
            </span>
          }
          sub={started && R ? R.dates[d] : "press Play (or space)"}
        />
        <Stat
          label="Inspections so far"
          tip="Identical for every policy: capacity × declarations of each day, rounded up."
          value={<AnimatedNumber value={insp} />}
          sub={`${capPct}% of ${num(declSoFar)} declarations`}
        />
        <Stat
          label="Hit rate"
          tip="Share of inspections that found a duty fraud (known after inspection)."
          value={<span style={{ color: COLORS.aiLight }}>{insp ? pct(aiF / insp) : "—"}</span>}
          sub={
            <span>
              rule <span style={{ color: COLORS.rule }}>{insp ? pct(ruleF / insp) : "—"}</span> · random{" "}
              {insp ? pct(rndF / insp) : "—"}
            </span>
          }
        />
        <Stat
          label="Safety threats caught"
          tip="Critical frauds (serious violations, e.g. unsafe goods) caught by the inspections, out of all threats present so far."
          value={
            <span>
              <span style={{ color: COLORS.aiLight }}>{aiT}</span>
              <span className="text-base text-slate-500"> / {threatsSoFar}</span>
            </span>
          }
          sub={
            <span>
              rule <span style={{ color: COLORS.rule }}>{ruleT}</span> · random {rndT}
            </span>
          }
        />
        <Stat
          label="Released green"
          tip="Declarations the AI sends to the green lane: no inspection, no document check. Faster clearance for compliant traders."
          value={<span style={{ color: COLORS.green }}>{declSoFar ? pct(greenSoFar / declSoFar) : "—"}</span>}
          sub="no inspection, no document check"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* Feed */}
        <Card className="flex flex-col lg:col-span-4 2xl:col-span-3">
          <CardHeader>
            <div>
              <CardTitle>Today's declarations</CardTitle>
              <CardDescription>
                {stream.data ? (
                  <>
                    {stream.data.date} · {num(stream.data.n)} declarations · {stream.data.capacity} inspections
                  </>
                ) : (
                  "Loading…"
                )}
              </CardDescription>
            </div>
            <div className="flex gap-1.5 text-[10px] tabular">
              {(["RED", "YELLOW", "GREEN"] as const).map((l) => (
                <span key={l} className="rounded px-1.5 py-0.5" style={{ color: LANE_META[l].color, background: `${LANE_META[l].color}14` }}>
                  {counts[l]}
                </span>
              ))}
            </div>
          </CardHeader>
          <CardContent className="thin-scroll max-h-[560px] flex-1 overflow-y-auto px-2 pb-3">
            {stream.error && !stream.data ? (
              <p className="p-4 text-sm text-slate-400">{stream.error}</p>
            ) : !stream.data ? (
              <div className="flex flex-col gap-2 p-2">
                {Array.from({ length: 8 }).map((_, i) => (
                  <Skeleton key={i} className="h-12" />
                ))}
              </div>
            ) : (
              <ul className="flex flex-col gap-0.5">
                <AnimatePresence initial={false} mode="popLayout">
                  {items.slice(0, FEED_MAX).map((it) => (
                    <FeedItem key={`${d}-${it.id}`} it={it} onOpen={() => open(it.id)} />
                  ))}
                </AnimatePresence>
                {items.length > FEED_MAX && (
                  <li className="px-3 py-2 text-center text-[11px] text-slate-500">
                    + {num(items.length - FEED_MAX)} more low-risk declarations released green
                  </li>
                )}
              </ul>
            )}
          </CardContent>
          <div className="border-t border-slate-800 px-4 py-2 text-[10px] text-slate-500">
            Click a declaration to open the inspector. Outcome icons (after inspection) are shown for the demo.
          </div>
        </Card>

        {/* Race */}
        <div className="flex flex-col gap-4 lg:col-span-8 2xl:col-span-9">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Same inspections, more fraud found</CardTitle>
                <CardDescription>
                  {R ? `${num(R.totals.inspections)} inspections over ${R.n_days} days for every policy at ${capPct}% capacity` : "…"}
                </CardDescription>
              </div>
              {started && (
                <motion.div
                  key={gain > 0 ? "pos" : "neg"}
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-lg border border-ai/40 bg-ai/10 px-3 py-1.5 text-right"
                >
                  <div className="text-lg font-semibold tabular text-ai-light">
                    {gain >= 0 ? "+" : "−"}
                    {num(Math.abs(gain))} frauds
                    {ruleF > 0 && <span className="ml-1 text-sm text-slate-300">({gain >= 0 ? "+" : "−"}{pct(Math.abs(gain) / ruleF)})</span>}
                  </div>
                  <div className="text-[11px] text-slate-400">AI vs current rule, same workload</div>
                </motion.div>
              )}
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <RaceCounter label={explore ? "RAQIB AI + explore" : "RAQIB AI"} color={COLORS.aiLight} value={aiF} rate={insp ? aiF / insp : null} big />
                <RaceCounter label="Current rule" hint="product history" color={COLORS.rule} value={ruleF} rate={insp ? ruleF / insp : null} big />
                <RaceCounter label="Random" hint="no targeting" color={COLORS.random} value={rndF} rate={insp ? rndF / insp : null} big />
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-x-8 gap-y-2 rounded-lg border border-slate-800 bg-slate-950/50 px-4 py-3">
                <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-slate-400">
                  <AlertTriangle className="h-4 w-4 text-lane-red" /> Public-safety threats caught
                  <InfoTip text="AI policy: declarations whose critical-fraud risk is in the top 1% take inspection slots first (public-safety alerts)." />
                </div>
                <div className="flex items-baseline gap-2">
                  <AnimatedNumber value={aiT} className="text-3xl font-bold text-ai-light" />
                  <span className="text-xs text-slate-400">AI</span>
                </div>
                <div className="flex items-baseline gap-2">
                  <AnimatedNumber value={ruleT} className="text-3xl font-bold" />
                  <span className="text-xs" style={{ color: COLORS.rule }}>
                    rule
                  </span>
                </div>
                <div className="flex items-baseline gap-2">
                  <AnimatedNumber value={rndT} className="text-2xl font-semibold text-slate-400" />
                  <span className="text-xs text-slate-500">random</span>
                </div>
                <div className="ml-auto text-xs text-slate-500">of {num(threatsSoFar)} threats present so far</div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Cumulative {metric === "frauds" ? "frauds" : "public-safety threats"} caught</CardTitle>
                <CardDescription>Day by day over the test period · identical capacity</CardDescription>
              </div>
              <div className="flex items-center gap-4">
                <div className="hidden items-center gap-3 text-xs text-slate-400 md:flex">
                  <span className="flex items-center gap-1.5"><Dot color={COLORS.ai} />AI</span>
                  <span className="flex items-center gap-1.5"><Dot color={COLORS.rule} />Rule</span>
                  <span className="flex items-center gap-1.5"><Dot color={COLORS.random} />Random</span>
                </div>
                <Segmented
                  value={metric}
                  onChange={setMetric}
                  options={[
                    { value: "frauds", label: "Frauds" },
                    { value: "threats", label: "Threats" },
                  ]}
                />
              </div>
            </CardHeader>
            <CardContent className="h-[300px] pt-1">
              {!R ? (
                <Skeleton className="h-full" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} interval={6} tickLine={false} axisLine={{ stroke: "#334155" }} />
                    <YAxis domain={[0, Math.ceil(yMax * 1.05)]} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} allowDecimals={false} />
                    <Tooltip
                      contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
                      labelStyle={{ color: "#cbd5e1" }}
                    />
                    <Line type="monotone" dataKey="random" name="Random" stroke={COLORS.random} strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey="rule" name="Rule" stroke={COLORS.rule} strokeWidth={2.5} dot={false} isAnimationActive={false} />
                    <Line type="monotone" dataKey="ai" name="AI" stroke={COLORS.ai} strokeWidth={3} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function RaceCounter({
  label,
  hint,
  color,
  value,
  rate,
  big,
}: {
  label: string;
  hint?: string;
  color: string;
  value: number;
  rate: number | null;
  big?: boolean;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/40 px-4 py-3">
      <div className="flex items-center gap-2 truncate text-[11px] font-semibold uppercase tracking-wider" style={{ color }}>
        <Dot color={color} /> {label}
        {hint && <span className="hidden font-normal normal-case tracking-normal text-slate-500 xl:inline">· {hint}</span>}
      </div>
      <AnimatedNumber value={value} className={cn("mt-1 block font-bold leading-none text-slate-50", big ? "text-5xl xl:text-6xl" : "text-4xl")} />
      <div className="mt-1.5 text-xs text-slate-400">
        frauds caught · hit rate <span className="tabular text-slate-300">{rate == null ? "—" : pct(rate)}</span>
      </div>
    </div>
  );
}

function FeedItem({ it, onOpen }: { it: StreamItem; onOpen: () => void }) {
  const color = LANE_META[it.lane].color;
  const inspected = it.lane === "RED";
  return (
    <motion.li
      layout="position"
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.25 }}
    >
      <button
        onClick={onOpen}
        className="group flex w-full cursor-pointer items-center gap-3 rounded-lg border border-transparent px-2.5 py-2 text-left transition-colors hover:border-slate-700 hover:bg-slate-800/50"
      >
        <span className="h-9 w-1 shrink-0 rounded-full" style={{ background: color }} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] text-slate-200" title={it.hs_desc}>
            {truncate(it.hs_desc, 70)}
          </div>
          <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-slate-500">
            <span className="font-mono">{it.hs6}</span>·<span>{it.origin}</span>·<span className="tabular">{compact(it.item_price)} KRW</span>
            {it.rule_selected && (
              <span className="rounded px-1 text-[9px] font-semibold" style={{ color: COLORS.rule, background: `${COLORS.rule}1f` }} title="The current rule would inspect this one">
                RULE
              </span>
            )}
            {it.explored && (
              <span className="rounded bg-slate-700/60 px-1 text-[9px] font-semibold text-slate-300" title="Random exploration pick">
                EXPLORE
              </span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <LaneBadge lane={it.lane} alert={it.alert} />
          <span className="flex items-center gap-1 text-[10px] tabular text-slate-400">
            {inspected &&
              (it.truth.fraud || it.truth.critical ? (
                <span className="flex items-center gap-0.5 text-lane-red" title="Inspection outcome: fraud found (demo)">
                  <Check className="h-3 w-3" /> found
                </span>
              ) : (
                <span className="text-slate-500" title="Inspection outcome: no fraud (demo)">clean</span>
              ))}
            <span>risk {pct(it.p_fraud)}</span>
          </span>
        </div>
      </button>
    </motion.li>
  );
}
