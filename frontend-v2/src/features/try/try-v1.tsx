import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Search, ShieldAlert, Sparkles, Wand2 } from "lucide-react";
import { useState } from "react";
import { useSearch } from "@tanstack/react-router";
import { WhatIfPanel } from "@/features/explainability/whatif";
import { TunisiaRefCard } from "@/components/raqib/tn-ref";
import { useMoney } from "@/lib/currency";
import { toast } from "sonner";
import { PageShell, UncertainBadge, WaterfallChart } from "@/components/raqib/kit";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  InfoTip,
  Skeleton,
} from "@/components/raqib/primitives";
import { Gauge, LaneBadge, ReasonList } from "@/components/raqib/visuals";
import { api, type DeclarationInput, type HsHit, type ScoreResult, type Waterfall } from "@/lib/api";

type ScoreV2 = ScoreResult & { waterfall: Waterfall; uncertain: boolean; disagreement: number };
import { pct, pctile, truncate } from "@/lib/format";
import { useApi, useDebounced } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { COLORS } from "@/lib/colors";

const OFFICES: [number, string][] = [
  [10, "Seoul Regional Customs"],
  [13, "Incheon Airport Intl. Postal Customs"],
  [16, "Pyeongtaek Customs"],
  [20, "Incheon Regional Customs (Port)"],
  [30, "Busan Regional Customs"],
  [40, "Incheon Regional Customs (Airport)"],
];
const TRANSPORT: [number, string][] = [
  [10, "Maritime"],
  [20, "Rail"],
  [30, "Road"],
  [40, "Air"],
  [50, "Mail"],
  [90, "Others"],
];

const EMPTY: DeclarationInput = {
  hs6: "",
  origin: "CN",
  office: 40,
  importer_id: "",
  declarant_id: "",
  seller_id: "",
  tax_rate: 8,
  net_mass: 100,
  item_price: 1_000_000,
  transport: 40,
};

const inputCls =
  "h-9 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none placeholder:text-muted-foreground/70 focus:border-ai disabled:opacity-50";

export function TryDeclaration() {
  const presets = useApi(() => api.presets(), "presets");
  const search = useSearch({ from: "/_authenticated/score" });
  const [form, setForm] = useState<DeclarationInput>(() => (search.hs6 ? { ...EMPTY, hs6: search.hs6 } : EMPTY));
  const [hsText, setHsText] = useState(search.hs6 ?? "");
  const [scored, setScored] = useState<DeclarationInput | null>(null);
  const [hsOpen, setHsOpen] = useState(false);
  const [newOps, setNewOps] = useState({ importer_id: true, declarant_id: true, seller_id: true });
  const [result, setResult] = useState<ScoreResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const money = useMoney();
  const shownValue = money.fromKrw(form.item_price);

  const q = useDebounced(hsText, 250);
  const hs = useApi<HsHit[]>(() => (q.trim().length >= 2 ? api.hsSearch(q.trim()) : Promise.resolve([])), `hs-${q}`);

  const set = <K extends keyof DeclarationInput>(k: K, v: DeclarationInput[K]) => setForm((f) => ({ ...f, [k]: v }));

  async function run(input: DeclarationInput) {
    if (!/^\d{4,6}$/.test(input.hs6)) {
      toast.error("Choose a product (HS6 code) first");
      return;
    }
    setBusy(true);
    try {
      const body = {
        ...input,
        importer_id: newOps.importer_id ? "" : (input.importer_id ?? ""),
        declarant_id: newOps.declarant_id ? "" : (input.declarant_id ?? ""),
        seller_id: newOps.seller_id ? "" : (input.seller_id ?? ""),
      };
      setResult(await api.score(body));
      setScored(body);
    } catch (e) {
      toast.error("Scoring failed", { description: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  }

  function applyPreset(key: string) {
    const p = presets.data?.find((x) => x.key === key);
    if (!p) return;
    setActivePreset(key);
    setForm(p.declaration);
    setHsText(`${p.declaration.hs6} · ${truncate(p.hs_desc, 60)}`);
    setNewOps({ importer_id: false, declarant_id: false, seller_id: false });
    setResult(null);
    setBusy(true);
    setScored(p.declaration);
    api
      .score(p.declaration)
      .then(setResult)
      .catch((e) => toast.error("Scoring failed", { description: String(e) }))
      .finally(() => setBusy(false));
  }

  return (
    <PageShell
        title="Try a declaration"
        why="Score a new import declaration in real time: lane, both risks and the reasons, from the same models used in the control room." actions={<>
        <div className="flex flex-wrap gap-2">
          {presets.data?.map((p) => (
            <Button
              key={p.key}
              variant={activePreset === p.key ? "default" : "outline"}
              size="sm"
              onClick={() => applyPreset(p.key)}
              title={`${p.description} (declaration ${p.source_declaration_id})`}
            >
              <Wand2 className="h-3.5 w-3.5" /> {p.label}
            </Button>
          ))}
          {presets.loading && !presets.data && <Skeleton className="h-8 w-80" />}
        </div>
      </>}>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        {/* Form */}
        <Card className="xl:col-span-5">
          <CardHeader>
            <div>
              <CardTitle>Declaration</CardTitle>
              <CardDescription>Presets are real declarations from the test period. Empty operator = new operator (no history).</CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <form
              className="flex flex-col gap-3"
              onSubmit={(e) => {
                e.preventDefault();
                run(form);
              }}
            >
              <label className="relative flex flex-col gap-1 text-xs text-muted-foreground">
                Product (HS6) — search by description or code
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <input
                    className={cn(inputCls, "pl-9")}
                    value={hsText}
                    placeholder="e.g. coffee, garments, 8517…"
                    onChange={(e) => {
                      setHsText(e.target.value);
                      setHsOpen(true);
                      setActivePreset(null);
                    }}
                    onFocus={() => setHsOpen(true)}
                    onBlur={() => window.setTimeout(() => setHsOpen(false), 150)}
                  />
                </div>
                {hsOpen && (hs.data?.length ?? 0) > 0 && (
                  <ul className="thin-scroll absolute top-full z-30 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-border bg-card shadow-2xl">
                    {hs.data!.map((h) => (
                      <li key={h.hs6}>
                        <button
                          type="button"
                          className="flex w-full cursor-pointer items-start gap-3 px-3 py-2 text-left text-xs hover:bg-muted"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => {
                            set("hs6", h.hs6);
                            setHsText(`${h.hs6} · ${truncate(h.description, 60)}`);
                            setHsOpen(false);
                          }}
                        >
                          <span className="font-mono text-ai-light">{h.hs6}</span>
                          <span className="flex-1 text-foreground">{h.description}</span>
                          <span className="shrink-0 text-muted-foreground">{h.past_declarations} past</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </label>

              <div className="grid grid-cols-3 gap-3">
                <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                  Origin (ISO)
                  <input
                    className={inputCls}
                    maxLength={2}
                    value={form.origin}
                    onChange={(e) => set("origin", e.target.value.toUpperCase())}
                  />
                </label>
                <label className="col-span-2 flex flex-col gap-1 text-xs text-muted-foreground">
                  Customs office
                  <select className={inputCls} value={form.office} onChange={(e) => set("office", Number(e.target.value))}>
                    {OFFICES.some(([c]) => c === form.office) ? null : <option value={form.office}>Office {form.office}</option>}
                    {OFFICES.map(([c, l]) => (
                      <option key={c} value={c}>
                        {c} · {l}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {(
                [
                  ["importer_id", "Importer ID"],
                  ["declarant_id", "Declarant ID"],
                  ["seller_id", "Seller ID"],
                ] as const
              ).map(([k, label]) => (
                <div key={k} className="grid grid-cols-3 items-end gap-3">
                  <label className="col-span-2 flex flex-col gap-1 text-xs text-muted-foreground">
                    {label}
                    <input
                      className={cn(inputCls, "font-mono")}
                      value={newOps[k] ? "" : (form[k] ?? "")}
                      disabled={newOps[k]}
                      placeholder={newOps[k] ? "new operator (no history)" : "e.g. QLRUBN9"}
                      onChange={(e) => {
                        set(k, e.target.value.trim().toUpperCase());
                        setActivePreset(null);
                      }}
                    />
                  </label>
                  <label className="flex h-9 cursor-pointer items-center gap-2 text-xs text-foreground/80">
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-[#2a78d6]"
                      checked={newOps[k]}
                      onChange={(e) => {
                        setNewOps((n) => ({ ...n, [k]: e.target.checked }));
                        setActivePreset(null);
                      }}
                    />
                    new operator
                  </label>
                </div>
              ))}

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                  Tax rate %
                  <input type="number" step="0.1" min={0} className={inputCls} value={form.tax_rate} onChange={(e) => set("tax_rate", Number(e.target.value))} />
                </label>
                <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                  Net mass kg
                  <input type="number" step="0.1" min={0} className={inputCls} value={form.net_mass} onChange={(e) => set("net_mass", Number(e.target.value))} />
                </label>
                <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                  Valeur {money.label}
                  <input
                    type="number"
                    step="0.01"
                    min={0}
                    className={inputCls}
                    value={Number.isFinite(shownValue) ? Math.round(shownValue * 100) / 100 : ""}
                    onChange={(e) => set("item_price", Math.max(0, money.toKrw(Number(e.target.value))) || 0)}
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-muted-foreground">
                  Transport
                  <select className={inputCls} value={form.transport} onChange={(e) => set("transport", Number(e.target.value))}>
                    {TRANSPORT.map(([c, l]) => (
                      <option key={c} value={c}>
                        {l}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <Button type="submit" size="lg" disabled={busy} className="mt-1">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                Score this declaration
              </Button>
              <p className="text-[11px] text-muted-foreground">
                Transport mode is recorded but not used by the model (not part of the recipe). Valeur saisie en {money.label}, convertie en KRW (unité du jeu de données) avant le calcul.
              </p>
            </form>
          </CardContent>
        </Card>

        {/* Result */}
        <div className="xl:col-span-7">
          <AnimatePresence mode="wait">
            {!result ? (
              <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <Card className="flex min-h-[420px] flex-col items-center justify-center gap-3 p-10 text-center">
                  {busy ? (
                    <Loader2 className="h-8 w-8 animate-spin text-ai-light" />
                  ) : (
                    <>
                      <ShieldAlert className="h-10 w-10 text-muted-foreground/70" />
                      <p className="text-sm text-foreground/80">Pick a preset or fill the form, then score.</p>
                      <p className="max-w-md text-xs text-muted-foreground">
                        RAQIB returns a lane (inspect / document check / release), the duty-fraud and public-safety probabilities
                        and the 4 strongest reasons, in about 100 ms.
                      </p>
                    </>
                  )}
                </Card>
              </motion.div>
            ) : (
              <motion.div key={JSON.stringify(result.input)} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                <Card>
                  <CardHeader>
                    <div>
                      <CardTitle>Result</CardTitle>
                      <CardDescription>
                        <span className="font-mono text-foreground/80">{result.input.hs6}</span> · {truncate(result.input.hs_description, 90)}
                      </CardDescription>
                    </div>
                    <motion.div initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: "spring", stiffness: 260, damping: 18 }}>
                      <LaneBadge lane={result.lane} alert={result.alert} size="lg" />
                    </motion.div>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-4">
                    <p className="text-sm text-foreground/80">{result.lane_reason}</p>
                    <div className="grid grid-cols-2 gap-2">
                      <Gauge
                        value={result.p_fraud}
                        label="Duty fraud"
                        sub={`higher than ${pctile(result.fraud_percentile)}% of test declarations`}
                        color={result.lane === "RED" ? COLORS.red : result.lane === "YELLOW" ? COLORS.yellow : COLORS.green}
                      />
                      <Gauge
                        value={result.p_critical}
                        label="Public-safety threat"
                        sub={`higher than ${pctile(result.critical_percentile)}% of test declarations`}
                        color={result.alert ? COLORS.red : COLORS.aiLight}
                      />
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                      <span>
                        RED from p(fraud) ≥ {pct(result.thresholds.red_p_fraud)} or safety alert p(critical) ≥ {pct(result.thresholds.alert_p_critical, 1)}
                      </span>
                      <span>YELLOW from p(fraud) ≥ {pct(result.thresholds.yellow_p_fraud)}</span>
                      <InfoTip text="Thresholds correspond to a 5% daily inspection capacity (RED), the next 10% (YELLOW) and the top 1% of public-safety risk, measured on the test period." />
                    </div>
                    {result.notes.length > 0 && (
                      <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs text-foreground/80">
                        {result.notes.map((n) => (
                          <div key={n}>• {n}</div>
                        ))}
                      </div>
                    )}
                    <div>
                      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Why — duty fraud</div>
                      <ReasonList reasons={result.reasons_fraud} compact />
                    </div>
                    <div>
                      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Public-safety signals</div>
                      <ReasonList reasons={result.reasons_critical} compact />
                    </div>
                    <TunisiaRefCard r={result.tunisia_ref} compact />
                    {(result as ScoreV2).uncertain && <UncertainBadge disagreement={(result as ScoreV2).disagreement} />}
                    {(result as ScoreV2).waterfall && (
                      <div>
                        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Exact waterfall — duty fraud</div>
                        <WaterfallChart w={(result as ScoreV2).waterfall} compact />
                      </div>
                    )}
                  </CardContent>
                </Card>
                {scored && (
                  <div className="mt-4">
                    <WhatIfPanel
                      key={JSON.stringify(scored)}
                      declaration={scored}
                      base={{ item_price: scored.item_price, net_mass: scored.net_mass, tax_rate: scored.tax_rate }}
                    />
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </PageShell>
  );
}
