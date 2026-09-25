import { motion } from "framer-motion";
import { useMemo, useState } from "react";
import type { NetLink, NetNode } from "@/lib/api";
import { num, pct } from "@/lib/format";
import { COLORS } from "@/lib/utils";

// Deterministic "hub" layout: declarant hub on the left, seller hub on the right, the
// declaration's importer in the middle; each hub's other importers fan out around it.

function riskColor(rate: number | null) {
  if (rate == null) return "#64748b";
  if (rate >= 0.4) return COLORS.red;
  if (rate >= 0.2) return COLORS.yellow;
  return COLORS.green;
}

export function NetworkGraph({ nodes, links, avg }: { nodes: NetNode[]; links: NetLink[]; avg: number }) {
  const [hover, setHover] = useState<string | null>(null);
  const W = 640;
  const H = 330;

  const pos = useMemo(() => {
    const p: Record<string, { x: number; y: number }> = {};
    const hasSeller = nodes.some((n) => n.type === "seller");
    const hubs = {
      declarant: { x: hasSeller ? 150 : 250, y: H / 2 },
      seller: { x: W - 150, y: H / 2 },
    };
    const focus = nodes.find((n) => n.is_focus);
    if (focus) p[focus.id] = { x: hasSeller ? W / 2 : 450, y: H / 2 };
    for (const n of nodes) {
      if (n.type === "declarant") p[n.id] = hubs.declarant;
      if (n.type === "seller") p[n.id] = hubs.seller;
    }
    for (const side of ["declarant", "seller"] as const) {
      const hub = nodes.find((n) => n.type === side);
      if (!hub) continue;
      const others = links
        .filter((l) => l.source === hub.id && l.target !== focus?.id && !p[l.target])
        .map((l) => l.target);
      const count = others.length;
      const base = side === "declarant" ? Math.PI : 0; // fan outward
      const spread = Math.PI * 0.95;
      others.forEach((id, i) => {
        const t = count === 1 ? 0.5 : i / (count - 1);
        const ang = base + (t - 0.5) * spread;
        const rad = 105 + (i % 2) * 22;
        p[id] = { x: hubs[side].x + rad * Math.cos(ang), y: hubs[side].y + rad * Math.sin(ang) };
      });
    }
    return p;
  }, [nodes, links]);

  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const maxLink = Math.max(1, ...links.map((l) => l.past_declarations));
  const hovered = hover ? byId[hover] : null;

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Operator network">
        {links.map((l, i) => {
          const a = pos[l.source];
          const b = pos[l.target];
          if (!a || !b) return null;
          const active = hover === l.source || hover === l.target;
          return (
            <motion.line
              key={i}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={active ? "#94a3b8" : "#334155"}
              strokeWidth={1 + 3 * (l.past_declarations / maxLink)}
              strokeDasharray={l.past_declarations === 0 ? "4 4" : undefined}
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: 0.9 }}
              transition={{ duration: 0.6, delay: 0.02 * i }}
            />
          );
        })}
        {nodes.map((n, i) => {
          const p = pos[n.id];
          if (!p) return null;
          const hub = n.type !== "importer";
          const r = hub ? 20 : n.is_focus ? 17 : 6 + Math.min(8, Math.log2(1 + n.past_declarations));
          const fill = hub ? "#0f172a" : riskColor(n.fraud_rate);
          return (
            <motion.g
              key={n.id}
              initial={{ opacity: 0, scale: 0.6 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.15 + 0.02 * i }}
              style={{ transformOrigin: `${p.x}px ${p.y}px` }}
              onMouseEnter={() => setHover(n.id)}
              onMouseLeave={() => setHover(null)}
              className="cursor-pointer"
            >
              {n.is_focus && <circle cx={p.x} cy={p.y} r={r + 7} fill="none" stroke={COLORS.aiLight} strokeWidth="2" strokeDasharray="4 3" />}
              <circle
                cx={p.x}
                cy={p.y}
                r={r}
                fill={fill}
                fillOpacity={hub ? 1 : 0.85}
                stroke={hub ? (n.type === "declarant" ? COLORS.ai : COLORS.rule) : "#0f172a"}
                strokeWidth={hub ? 2.5 : 1.5}
              />
              {hub && (
                <text x={p.x} y={p.y + 4} textAnchor="middle" style={{ fontSize: 10, fontWeight: 700 }} className="fill-slate-100">
                  {n.type === "declarant" ? "DECL" : "SELL"}
                </text>
              )}
              {(hub || n.is_focus) && (
                <text x={p.x} y={p.y + r + 14} textAnchor="middle" style={{ fontSize: 10 }} className="fill-slate-300 font-mono">
                  {n.label}
                </text>
              )}
            </motion.g>
          );
        })}
      </svg>
      <div className="pointer-events-none absolute left-3 top-2 min-h-[44px] text-xs">
        {hovered ? (
          <div className="rounded-md border border-slate-700 bg-slate-900/95 px-2.5 py-1.5 shadow-lg">
            <div className="font-mono text-slate-100">
              {hovered.type} {hovered.label} {hovered.is_focus && <span className="text-ai-light">(this declaration)</span>}
            </div>
            <div className="text-slate-400">
              {num(hovered.past_declarations)} past declarations ·{" "}
              {hovered.fraud_rate == null ? "no history" : `${pct(hovered.fraud_rate)} fraud (avg ${pct(avg)})`}
            </div>
          </div>
        ) : (
          <div className="text-slate-500">Hover a node for its history</div>
        )}
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-400">
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS.red }} />importer ≥40% fraud</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS.yellow }} />20–40%</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS.green }} />&lt;20%</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-slate-500" />no history</span>
        <span>line width = past declarations together</span>
      </div>
    </div>
  );
}
