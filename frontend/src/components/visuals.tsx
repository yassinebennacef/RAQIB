import { animate, motion } from "framer-motion";
import { AlertTriangle, ArrowDownRight, ArrowUpRight } from "lucide-react";
import { useEffect, useRef } from "react";
import type { Lane, Reason } from "@/lib/api";
import { num } from "@/lib/format";
import { LANE_META } from "@/lib/lanes";
import { cn, COLORS } from "@/lib/utils";

/* ------------------------------------------------------------------ Logo */
export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#0b1220" />
      <circle cx="16" cy="16" r="11" fill="none" stroke={COLORS.ai} strokeWidth="1.6" opacity=".45" />
      <circle cx="16" cy="16" r="6.5" fill="none" stroke={COLORS.ai} strokeWidth="1.6" opacity=".75" />
      <g className="radar-sweep">
        <path d="M16 16 L25 9" stroke={COLORS.aiLight} strokeWidth="1.8" strokeLinecap="round" />
        <path d="M16 16 L25 9 A11 11 0 0 1 27 16 Z" fill={COLORS.ai} opacity=".18" />
      </g>
      <circle cx="16" cy="16" r="2.3" fill="#e2e8f0" />
      <circle cx="22.5" cy="20.5" r="1.9" fill={COLORS.red} />
    </svg>
  );
}

/* ------------------------------------------------------------------ Lane badge */
export function LaneBadge({ lane, size = "sm", alert = false }: { lane: Lane; size?: "sm" | "lg"; alert?: boolean }) {
  const m = LANE_META[lane];
  const Icon = alert ? AlertTriangle : m.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-semibold tracking-wide",
        size === "lg" ? "px-4 py-1.5 text-sm" : "px-2 py-0.5 text-[10px]",
      )}
      style={{ color: m.color, borderColor: `${m.color}66`, background: `${m.color}1a` }}
    >
      <Icon className={size === "lg" ? "h-4 w-4" : "h-3 w-3"} />
      {m.label}
      <span className="font-medium opacity-80">· {alert && lane === "RED" ? "Safety alert" : m.action}</span>
    </span>
  );
}

/* ------------------------------------------------------------------ Animated number */
export function AnimatedNumber({
  value,
  format = (v: number) => num(Math.round(v)),
  className,
  duration = 0.5,
}: {
  value: number;
  format?: (v: number) => string;
  className?: string;
  duration?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const prev = useRef(value);
  const fmt = useRef(format);
  fmt.current = format;
  useEffect(() => {
    const controls = animate(prev.current, value, {
      duration,
      ease: "easeOut",
      onUpdate: (v) => {
        if (ref.current) ref.current.textContent = fmt.current(v);
      },
    });
    prev.current = value;
    return () => controls.stop();
  }, [value, duration]);
  return (
    <span ref={ref} className={cn("tabular", className)}>
      {format(value)}
    </span>
  );
}

/* ------------------------------------------------------------------ Gauge */
export function Gauge({
  value,
  label,
  sub,
  color,
  marker,
  markerLabel,
}: {
  value: number;
  label: string;
  sub?: string;
  color: string;
  marker?: number;
  markerLabel?: string;
}) {
  const r = 70;
  const cx = 90;
  const cy = 88;
  const len = Math.PI * r;
  const v = Math.max(0, Math.min(1, value));
  const arc = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`;
  const mAngle = marker != null ? Math.PI * (1 - Math.max(0, Math.min(1, marker))) : null;
  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 180 104" className="w-full max-w-[220px]" role="img" aria-label={`${label}: ${(v * 100).toFixed(0)}%`}>
        <path d={arc} fill="none" stroke="#1e293b" strokeWidth="14" strokeLinecap="round" />
        <motion.path
          d={arc}
          fill="none"
          stroke={color}
          strokeWidth="14"
          strokeLinecap="round"
          strokeDasharray={len}
          initial={{ strokeDashoffset: len }}
          animate={{ strokeDashoffset: len * (1 - v) }}
          transition={{ duration: 0.9, ease: "easeOut" }}
          style={{ filter: `drop-shadow(0 0 6px ${color}55)` }}
        />
        {mAngle != null && (
          <g>
            <line
              x1={cx + (r - 12) * Math.cos(mAngle)}
              y1={cy - (r - 12) * Math.sin(mAngle)}
              x2={cx + (r + 12) * Math.cos(mAngle)}
              y2={cy - (r + 12) * Math.sin(mAngle)}
              stroke="#e2e8f0"
              strokeWidth="2"
              strokeDasharray="3 2"
            />
            {markerLabel && (
              <title>{markerLabel}</title>
            )}
          </g>
        )}
        <text x={cx} y={cy - 14} textAnchor="middle" className="fill-slate-50" style={{ fontSize: 30, fontWeight: 650 }}>
          {(v * 100).toFixed(v < 0.1 ? 1 : 0)}%
        </text>
        <text x={cx} y={cy + 4} textAnchor="middle" className="fill-slate-400" style={{ fontSize: 10 }}>
          probability
        </text>
      </svg>
      <div className="-mt-1 text-center">
        <div className="text-sm font-medium text-slate-200">{label}</div>
        {sub && <div className="text-xs text-slate-400">{sub}</div>}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Reasons with contribution bars */
export function ReasonList({ reasons, compact = false }: { reasons: Reason[]; compact?: boolean }) {
  const max = Math.max(...reasons.map((r) => Math.abs(r.contribution)), 0.01);
  return (
    <ol className={cn("flex flex-col", compact ? "gap-2" : "gap-3")}>
      {reasons.map((r, i) => {
        const up = r.direction === "raises";
        const color = up ? COLORS.red : COLORS.green;
        const Icon = up ? ArrowUpRight : ArrowDownRight;
        return (
          <motion.li
            key={`${r.group}-${i}`}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="rounded-lg border border-slate-800 bg-slate-950/40 p-3"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider" style={{ color }}>
                <Icon className="h-3.5 w-3.5" />
                {up ? "Raises risk" : "Lowers risk"} · {r.label}
              </div>
              <div className="flex h-1.5 w-28 overflow-hidden rounded-full bg-slate-800">
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: color }}
                  initial={{ width: 0 }}
                  animate={{ width: `${(Math.abs(r.contribution) / max) * 100}%` }}
                  transition={{ duration: 0.6, delay: i * 0.08 }}
                />
              </div>
            </div>
            <p className={cn("mt-1.5 leading-snug text-slate-200", compact ? "text-xs" : "text-sm")}>{r.text}</p>
          </motion.li>
        );
      })}
    </ol>
  );
}

/* ------------------------------------------------------------------ Legend dot */
export function Dot({ color, className }: { color: string; className?: string }) {
  return <span className={cn("inline-block h-2.5 w-2.5 rounded-full", className)} style={{ background: color }} />;
}
