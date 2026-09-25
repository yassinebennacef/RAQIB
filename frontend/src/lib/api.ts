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
    fraud: { auc: number; precision_at_5: number; recall_at_5: number };
    critical: { auc: number; precision_at_5: number; recall_at_5: number };
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
