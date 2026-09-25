const nf0 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1, minimumFractionDigits: 1 });

export const num = (x: number | null | undefined) => (x == null || Number.isNaN(x) ? "—" : nf0.format(x));

export const pct = (x: number | null | undefined, digits = 0) =>
  x == null || Number.isNaN(x) ? "—" : `${(x * 100).toFixed(digits)}%`;

export const pts = (x: number | null | undefined, digits = 1) =>
  x == null || Number.isNaN(x) ? "—" : `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(digits)} pts`;

export const dec = (x: number | null | undefined, digits = 2) =>
  x == null || Number.isNaN(x) ? "—" : x.toFixed(digits);

export function compact(x: number | null | undefined): string {
  if (x == null || Number.isNaN(x)) return "—";
  const a = Math.abs(x);
  if (a >= 1e9) return `${nf1.format(x / 1e9)}B`;
  if (a >= 1e6) return `${nf1.format(x / 1e6)}M`;
  if (a >= 1e4) return `${nf1.format(x / 1e3)}k`;
  if (a >= 100) return nf0.format(x);
  return x.toFixed(1);
}

export const krw = (x: number | null | undefined) => `${compact(x)} KRW`;

export const shortHash = (h: string, n = 10) => (h ? h.slice(0, n) : "");

export function truncate(s: string, n: number) {
  const t = (s || "").replace(/\s+/g, " ").trim();
  return t.length <= n ? t : `${t.slice(0, n - 1).trimEnd()}…`;
}

/** "higher than X% of declarations" without ever printing 100%. */
export const pctile = (p: number) => (p >= 99 ? Math.min(p, 99.9).toFixed(1) : p.toFixed(0));
