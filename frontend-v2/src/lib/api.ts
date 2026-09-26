// Typed client for the RAQIB API (see API.md). Every number on screen comes from here.

export type Lane = "RED" | "YELLOW" | "GREEN";
export type PolicyKey = "ai" | "ai_explore" | "rule" | "random";
export type TargetKey = "fraud" | "critical";
export type MethodKey = "ai" | "rule_hs6_history" | "rule_importer_history" | "random";

export interface Health {
  status: "ok" | "degraded";
  models_loaded: boolean;
  artifacts: Record<string, boolean>;
  n_test_declarations: number;
  n_days: number;
  error: string | null;
  frontend_built: boolean;
}

export interface PolicySummary {
  inspections: number;
  frauds: number;
  threats: number;
  hit_rate: number;
  fraud_recall: number;
  threat_recall: number;
  distinct_hs6: number;
  explored: number;
  explored_frauds: number;
  green_share?: number;
  yellow_share?: number;
}

export interface PolicySeries {
  label: string;
  frauds: number[];
  threats: number[];
  cum_frauds: number[];
  cum_threats: number[];
  cum_inspected: number[];
  distinct_hs6: number[];
  explored: number[];
  explored_frauds: number[];
  red?: number[];
  yellow?: number[];
  green?: number[];
  alerts?: number[];
  summary: PolicySummary;
}

export interface Replay {
  rate: number;
  explore: number;
  seed: number;
  n_days: number;
  dates: string[];
  n: number[];
  capacity: number[];
  day_frauds: number[];
  day_threats: number[];
  alert_threshold: number;
  totals: { declarations: number; frauds: number; threats: number; inspections: number };
  policies: Record<PolicyKey, PolicySeries>;
}

export interface StreamItem {
  id: string;
  hs6: string;
  hs_desc: string;
  origin: string;
  office_label: string;
  transport_label: string;
  item_price: number;
  net_mass: number;
  lane: Lane;
  alert: boolean;
  explored: boolean;
  rule_selected: boolean;
  p_fraud: number;
  p_critical: number;
  rank_in_day: number;
  top_reason: string;
  truth: { fraud: number; critical: number };
}

export interface Stream {
  day: number;
  date: string;
  n: number;
  capacity: number;
  rate: number;
  explore: number;
  items: StreamItem[];
  truth_note: string;
}

export interface Reason {
  group: string;
  label: string;
  text: string;
  contribution: number;
  direction: "raises" | "lowers";
  thin_history: boolean;
}

export interface OperatorHistory {
  id: string | null;
  role: string;
  past_declarations: number;
  is_new: boolean;
  missing?: boolean;
  fraud_rate: number | null;
  critical_rate: number | null;
  thin_history: boolean;
}

export interface NetNode {
  id: string;
  type: "importer" | "declarant" | "seller";
  label: string;
  is_focus: boolean;
  past_declarations: number;
  fraud_rate: number | null;
}

export interface NetLink {
  source: string;
  target: string;
  past_declarations: number;
}

export interface DecisionEntry {
  id: number;
  ts: string;
  declaration_id: string;
  decision: "INSPECT" | "DOCUMENT_CHECK" | "RELEASE";
  comment: string;
  officer: string;
  ai: { lane?: string; p_fraud?: number; p_critical?: number };
  prev_hash: string;
  hash: string;
}

export interface DeclarationDetail {
  declaration: {
    id: string;
    date: string;
    hs6: string;
    hs_desc: string;
    office: number;
    office_label: string;
    transport: number;
    transport_label: string;
    origin: string;
    departure: string;
    importer: string;
    declarant: string;
    seller: string | null;
    courier: string | null;
    process_type: string;
    import_type: number;
    import_use: number;
    payment_type: number;
    tax_type: string;
    origin_indicator: string;
    tax_rate: number;
    net_mass: number;
    item_price: number;
    unit_value: number;
  };
  ai: {
    p_fraud: number;
    p_critical: number;
    fraud_percentile: number;
    critical_percentile: number;
    lane: Lane;
    alert: boolean;
    explored: boolean;
    lane_reason: string;
    rank_in_day: number;
    reasons_fraud: Reason[];
    reasons_critical: Reason[];
  };
  rule: {
    name: string;
    score: number;
    hs6_past_declarations: number;
    hs6_past_fraud_rate: number | null;
    rank_in_day: number;
    selected: boolean;
    decision: "INSPECT" | "RELEASE";
    explanation: string;
  };
  day: { index: number; date: string; n: number; capacity: number; rate: number };
  truth: { fraud: number; critical: number; critical_code: number; note: string };
  history: {
    importer: OperatorHistory;
    declarant: OperatorHistory;
    seller: OperatorHistory;
    average_fraud_rate: number;
  };
  network: { nodes: NetNode[]; links: NetLink[]; note: string };
  decisions: DecisionEntry[];
}

export interface DeclarationInput {
  hs6: string;
  origin: string;
  office: number;
  importer_id: string;
  declarant_id: string;
  seller_id: string;
  tax_rate: number;
  net_mass: number;
  item_price: number;
  transport: number;
}

export interface ScoreResult {
  input: DeclarationInput & { hs_description: string; office_label: string; transport_label: string };
  p_fraud: number;
  p_critical: number;
  fraud_percentile: number;
  critical_percentile: number;
  alert: boolean;
  lane: Lane;
  lane_reason: string;
  reasons_fraud: Reason[];
  reasons_critical: Reason[];
  notes: string[];
  thresholds: { red_p_fraud: number; yellow_p_fraud: number; alert_p_critical: number };
  transport_used_by_model: boolean;
}

export interface Preset {
  key: string;
  label: string;
  description: string;
  source_declaration_id: string;
  declaration: DeclarationInput;
  hs_desc: string;
}

export interface HsHit {
  hs6: string;
  description: string;
  past_declarations: number;
}

export interface MethodMetrics {
  auc: number;
  precision_at_1: number;
  precision_at_5: number;
  precision_at_10: number;
  recall_at_1: number;
  recall_at_5: number;
  recall_at_10: number;
  caught_at_1: number;
  caught_at_5: number;
  caught_at_10: number;
  k_at_1: number;
  k_at_5: number;
  k_at_10: number;
  precision_se_at_5: number;
  recall_se_at_1: number;
  recall_se_at_5: number;
  recall_se_at_10: number;
}

export interface WeeklyRow {
  week: number;
  start: string;
  n: number;
  positives: number;
  base_rate: number;
  precision_ai: number;
  recall_ai: number | null;
  precision_rule: number;
  recall_rule: number | null;
}

export interface TargetMetrics {
  label: string;
  base_rate: number;
  n_positive: number;
  prior_train: number;
  methods: Record<MethodKey, MethodMetrics>;
  calibration: { bin: number; n: number; mean_predicted: number; observed: number }[];
  weekly: WeeklyRow[];
  importance: {
    features: { feature: string; share: number }[];
    groups: { group: string; label: string; share: number }[];
  };
  gain_vs_rule: { metric: string; mean_gain: number; ci95: [number, number]; n_boot: number; share_boot_ai_better: number };
}

export interface FairnessRow {
  code: string;
  label: string;
  n: number;
  share_declarations: number;
  share_inspections_ai: number;
  share_inspections_rule: number;
  selection_rate_ai: number;
  selection_rate_rule: number;
  fraud_rate: number;
}

export interface Metrics {
  generated_at: string;
  recipe: { train: string[]; test: string[]; n_train: number; n_test: number; features: string[] };
  method_labels: Record<MethodKey, string>;
  targets: Record<TargetKey, TargetMetrics>;
  fairness: {
    k: number;
    share: number;
    office: { rows: FairnessRow[]; max_min_selection_ratio_ai: number | null };
    transport: { rows: FairnessRow[]; max_min_selection_ratio_ai: number | null };
  };
  n_critical_test: number;
  ablation_no_value: {
    removed: string[];
    fraud: { auc: number; precision_at_5: number; recall_at_5: number; full_auc: number; full_precision_at_5: number; full_recall_at_5: number };
    critical: { auc: number; precision_at_5: number; recall_at_5: number; full_auc: number; full_precision_at_5: number; full_recall_at_5: number };
  };
  thresholds: { red_p_fraud: number; yellow_p_fraud: number; alert_p_critical: number };
  replay_summary: {
    rate: number;
    explore: number;
    n_days: number;
    totals: { declarations: number; frauds: number; threats: number; inspections: number };
    policies: Record<PolicyKey, PolicySummary & { label: string }>;
  };
}

export interface SplitCard {
  rows: number;
  period: [string, string];
  days: number;
  fraud_rate: number;
  critical_rate: number;
  n_fraud: number;
  n_critical: number;
}

export interface DataCard {
  dataset: string;
  licence: string;
  source_url: string;
  hs_names: { source_url: string; licence: string };
  rows: number;
  columns: number;
  train: SplitCard;
  test: SplitCard;
  unique: Record<"importers" | "declarants" | "sellers" | "hs6" | "origins" | "offices", number>;
  fraud_rate: number;
  critical_rate: number;
  hs_name_match: { hs6: number; hs4_fallback: number; none: number };
  test_new_operators: Record<"importer" | "declarant" | "seller" | "hs6", number>;
  missing_seller_share: number;
  test_unit_value_equals_product_median: number;
  notes: string[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

const post = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const api = {
  health: () => request<Health>("/health"),
  metrics: () => request<Metrics>("/metrics"),
  dataCard: () => request<DataCard>("/data-card"),
  replay: (rate: number, explore: number) => request<Replay>(`/replay?rate=${rate}&explore=${explore}`),
  stream: (day: number, rate: number, explore: number) =>
    request<Stream>(`/stream?day=${day}&rate=${rate}&explore=${explore}`),
  declaration: (id: string, rate = 0.05, explore = 0) =>
    request<DeclarationDetail>(`/declaration/${encodeURIComponent(id)}?rate=${rate}&explore=${explore}`),
  score: (body: DeclarationInput) => post<ScoreResult>("/score", body),
  presets: () => request<Preset[]>("/presets"),
  hsSearch: (q: string) => request<HsHit[]>(`/hs/search?q=${encodeURIComponent(q)}`),
  decide: (body: { declaration_id: string; decision: DecisionEntry["decision"]; comment: string; officer: string }) =>
    post<{ id: number; hash: string; prev_hash: string; ts: string }>("/decision", body),
  decisions: () =>
    request<{ entries: DecisionEntry[]; verify: { ok: boolean; n_entries: number; first_bad_id: number | null } }>(
      "/decisions",
    ),
};


// ============================================================================ v2 (see API.md "v2 additions")
export type ModelKey = "lightgbm" | "ebm";

export interface WaterfallStep {
  group: string;
  label: string;
  contribution: number;
  delta: number;
  cumulative: number;
}

export interface Waterfall {
  model: ModelKey;
  target: TargetKey;
  base: number;
  final: number;
  steps: WaterfallStep[];
  other: { contribution: number; delta: number };
  note: string;
}

export interface TwinModels {
  primary: Record<TargetKey, ModelKey>;
  lightgbm: { p_fraud: number; p_critical: number };
  ebm: { p_fraud: number; p_critical: number };
}

export type DeclarationDetailV2 = DeclarationDetail & {
  ai: DeclarationDetail["ai"] & { uncertain: boolean; disagreement: number; models: TwinModels };
  waterfall: Waterfall;
  waterfall_critical: Waterfall;
  network: DeclarationDetail["network"] & { context_only?: boolean };
};

export type StreamItemV2 = StreamItem & { uncertain: boolean; disagreement: number };

export interface WorklistItem {
  id: string;
  date: string;
  day: number;
  hs6: string;
  hs_desc: string;
  hs2: string;
  origin: string;
  office: number;
  office_label: string;
  transport_label: string;
  item_price: number;
  lane: Lane;
  alert: boolean;
  uncertain: boolean;
  disagreement: number;
  p_fraud: number;
  p_critical: number;
  top_reason: string;
  rule_decision: "INSPECT" | "RELEASE";
  truth: { fraud: number; critical: number };
}

export interface FacetValue {
  value: string;
  n: number;
  label?: string;
}

export interface Worklist {
  total: number;
  page: number;
  page_size: number;
  facets: {
    lane: Partial<Record<Lane, number>>;
    uncertain: Record<string, number>;
    origin: FacetValue[];
    office: FacetValue[];
    hs2: FacetValue[];
  };
  items: WorklistItem[];
}

export interface WorklistQuery {
  day?: number;
  lane?: string;
  origin?: string;
  hs2?: string;
  office?: string;
  uncertain?: boolean;
  min_p?: number;
  q?: string;
  sort?: string;
  order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export interface WhatIfChanges {
  item_price?: number;
  net_mass?: number;
  tax_rate?: number;
  origin?: string;
  hs6?: string;
  importer?: string;
  declarant?: string;
  seller?: string;
}

export interface WhatIfSide {
  p_fraud: number;
  p_critical: number;
  lane: Lane;
  lane_reason: string;
  alert: boolean;
  uncertain: boolean;
  disagreement: number;
  waterfall: Waterfall;
  reasons_fraud: Reason[];
}

export interface WhatIfResult {
  before: WhatIfSide;
  after: WhatIfSide;
  deltas: { group: string; label: string; before: number; after: number; delta: number }[];
  changed: string[];
  note: string;
}

export interface CurvePoint {
  rate: number;
  inspections: number;
  ai: { frauds: number; threats: number };
  rule: { frauds: number; threats: number };
  random: { frauds: number; threats: number };
}

export interface Efficiency {
  curve: CurvePoint[];
  matching: {
    reference: { policy: string; rate: number; frauds: number; threats: number; inspections: number };
    ai_rate: number;
    ai_inspections: number;
    ai_frauds: number;
    ai_threats: number;
    fewer_inspections: number;
    fewer_pct: number;
  };
  pooled: { k_rule: number; rule_frauds: number; k_ai_needed: number; fewer_inspections: number; fewer_pct: number };
  threats: { rule_at_ref: number; ai_rate_matching_threats: number | null; ai_inspections: number | null };
  officer_hours: {
    minutes_per_inspection: number;
    assumption: boolean;
    hours_freed_test_period: number;
    test_days: number;
    hours_freed_per_year: number;
    note: string;
  };
  policy_note: string;
}

export interface Experiment {
  key: "ebm" | "disagreement" | "isolation_forest" | "network_2hop";
  title: string;
  decision: "kept" | "rejected";
  hypothesis: string;
  method: string;
  result: Record<string, number | string[] | null | Record<string, unknown>>;
  baseline?: Record<string, number>;
  reason: string;
}

export interface ShapePoint {
  x: number;
  y: number;
  lower: number;
  upper: number;
}

export interface XaiTarget {
  model: ModelKey;
  intercept: number;
  base_rate: number;
  importances: { term: string; label: string; group: string | null; importance: number; share: number }[];
  shapes: {
    term: string;
    label: string;
    group: string | null;
    x_label: string;
    x_scale: "linear" | "log";
    y_label: string;
    points: ShapePoint[];
  }[];
}

export interface XaiGlobal {
  primary_model: Record<TargetKey, ModelKey>;
  targets: Record<TargetKey, XaiTarget>;
}

export interface ModelCardSection {
  key: string;
  title: string;
  text?: string;
  bullets?: string[];
  table?: { columns: string[]; rows: (string | number)[][] };
}

export interface ModelCard {
  title: string;
  version: string;
  generated_at: string;
  sections: ModelCardSection[];
}

export interface Brief {
  id: string;
  lang: "fr" | "en" | "ar";
  text: string;
  source: "template" | "llm";
  model: string | null;
  cached: boolean;
}

export type MetricsV2 = Metrics & {
  primary_model: Record<TargetKey, ModelKey> & { rule: string };
  targets: Record<TargetKey, TargetMetrics & {
    methods: TargetMetrics["methods"] & { lightgbm: MethodMetrics; ebm: MethodMetrics };
    ebm_vs_lightgbm: TargetMetrics["gain_vs_rule"];
    calibration_models: Record<ModelKey, TargetMetrics["calibration"]>;
  }>;
  uncertainty: {
    threshold: number;
    n_flagged: number;
    share_flagged: number;
    fraud_rate_flagged: number | null;
    fraud_rate_all: number;
    green_to_yellow: number;
    fraud_rate_green_to_yellow: number | null;
    fraud_rate_green_after: number;
  };
};

function qs(params: Record<string, unknown>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") u.set(k, String(v));
  const s = u.toString();
  return s ? `?${s}` : "";
}

export const apiV2 = {
  declaration: (id: string, rate = 0.05, explore = 0) =>
    request<DeclarationDetailV2>(`/declaration/${encodeURIComponent(id)}?rate=${rate}&explore=${explore}`),
  stream: (day: number, rate: number, explore: number) =>
    request<Omit<Stream, "items"> & { items: StreamItemV2[] }>(`/stream?day=${day}&rate=${rate}&explore=${explore}`),
  worklist: (q: WorklistQuery) => request<Worklist>(`/worklist${qs(q as Record<string, unknown>)}`),
  whatif: (body: { declaration_id?: string; declaration?: DeclarationInput; changes: WhatIfChanges }) =>
    post<WhatIfResult>("/whatif", body),
  efficiency: (minutes = 60) => request<Efficiency>(`/efficiency?minutes_per_inspection=${minutes}`),
  experiments: () => request<{ experiments: Experiment[] }>("/experiments"),
  xaiGlobal: () => request<XaiGlobal>("/xai-global"),
  modelCard: () => request<ModelCard>("/model-card"),
  brief: (id: string, lang: "fr" | "en" | "ar") => post<Brief>(`/brief/${encodeURIComponent(id)}?lang=${lang}`, {}),
  metrics: () => request<MetricsV2>("/metrics"),
};
