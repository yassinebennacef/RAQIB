import { animate, motion } from 'framer-motion'
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Info, Scale } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { Lane, Reason, Waterfall } from '@/lib/api'
import { useMoney } from '@/lib/currency'
import { COLORS } from '@/lib/colors'
import { num, pct } from '@/lib/format'
import { LANE_META } from '@/lib/lanes'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ConfigDrawer } from '@/components/config-drawer'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { CurrencySwitch } from './currency-switch'
import { LlmDot } from './llm-dot'

/* ------------------------------------------------------------------ Page shell */
export function PageShell({
  title,
  why,
  actions,
  children,
}: {
  title: string
  why: string
  actions?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <>
      <Header fixed>
        <Search placeholder='Déclaration, produit ou page…' />
        <div className='ms-auto flex items-center gap-2'>
          <Badge variant='outline' className='hidden border-primary/40 text-primary lg:inline-flex'>
            Données publiques · aucune donnée confidentielle
          </Badge>
          <CurrencySwitch />
          <LlmDot />
          <ThemeSwitch />
          <ConfigDrawer />
          <span className='hidden items-center gap-2 rounded-full border px-2 py-1 text-xs text-muted-foreground xl:flex'>
            <span className='flex size-5 items-center justify-center rounded-full bg-primary/20 text-[10px] font-semibold text-primary'>
              AG
            </span>
            Agent · Office 30 (demo)
          </span>
        </div>
      </Header>
      <Main fluid className='flex flex-col gap-4'>
        <div className='flex flex-wrap items-end justify-between gap-3'>
          <div>
            <h1 className='text-2xl font-bold tracking-tight'>{title}</h1>
            <p className='mt-0.5 text-sm text-muted-foreground'>{why}</p>
          </div>
          {actions}
        </div>
        {children}
        <footer className='mt-6 border-t pt-3 text-center text-[11px] text-muted-foreground'>
          RAQIB · Ciblage des contrôles — prototype conçu pour la Douane tunisienne (outil d'aide : l'agent
          décide) · Déclarations : jeu public MIT (Korea Customs Service / IBS), montants convertis depuis le KRW ·
          Données réelles publiques : UN Comtrade (Tunisie) · aucune donnée confidentielle
        </footer>
      </Main>
    </>
  )
}

/* ------------------------------------------------------------------ Small pieces */
export function InfoTip({ text }: { text: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button type='button' aria-label={text} className='inline-flex text-muted-foreground hover:text-foreground'>
          <Info className='size-3.5' />
        </button>
      </TooltipTrigger>
      <TooltipContent className='max-w-72 text-xs leading-relaxed'>{text}</TooltipContent>
    </Tooltip>
  )
}

export function Dot({ color, className }: { color: string; className?: string }) {
  return <span className={cn('inline-block size-2.5 rounded-full', className)} style={{ background: color }} />
}

export function Stat({
  label,
  value,
  sub,
  tip,
  className,
}: {
  label: string
  value: React.ReactNode
  sub?: React.ReactNode
  tip?: string
  className?: string
}) {
  return (
    <Card className={cn('gap-1 px-4 py-3', className)}>
      <div className='flex items-center gap-1.5 text-[11px] font-medium tracking-wider text-muted-foreground uppercase'>
        {label}
        {tip && <InfoTip text={tip} />}
      </div>
      <div className='text-2xl font-semibold tabular-nums'>{value}</div>
      {sub && <div className='text-xs text-muted-foreground'>{sub}</div>}
    </Card>
  )
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T
  options: { value: T; label: React.ReactNode }[]
  onChange: (v: T) => void
}) {
  return (
    <div role='tablist' className='inline-flex rounded-lg border bg-muted/40 p-0.5'>
      {options.map((o) => (
        <button
          key={o.value}
          role='tab'
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
            value === o.value ? 'bg-background text-foreground shadow' : 'text-muted-foreground hover:text-foreground'
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function RangeSlider({
  value,
  min,
  max,
  step = 1,
  onChange,
  label,
}: {
  value: number
  min: number
  max: number
  step?: number
  onChange: (v: number) => void
  label: string
}) {
  const fill = `${((value - min) / (max - min)) * 100}%`
  return (
    <input
      type='range'
      aria-label={label}
      className='raqib-range'
      style={{ ['--fill' as string]: fill } as React.CSSProperties}
      min={min}
      max={max}
      step={step}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
    />
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Card className='items-center gap-2 border-destructive/40 p-8 text-center'>
      <p className='text-sm'>Could not load data from the RAQIB API.</p>
      <p className='font-mono text-xs text-muted-foreground'>{message}</p>
      <p className='text-xs text-muted-foreground'>
        Is the backend running? <code className='font-mono'>python -m raqib.serve</code>
      </p>
      {onRetry && (
        <Button variant='outline' size='sm' onClick={onRetry}>
          Retry
        </Button>
      )}
    </Card>
  )
}

/* ------------------------------------------------------------------ Lanes */
export function LaneBadge({ lane, size = 'sm', alert = false }: { lane: Lane; size?: 'sm' | 'lg'; alert?: boolean }) {
  const m = LANE_META[lane]
  const Icon = alert ? AlertTriangle : m.icon
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border font-semibold tracking-wide whitespace-nowrap',
        size === 'lg' ? 'px-4 py-1.5 text-sm' : 'px-2 py-0.5 text-[10px]'
      )}
      style={{ color: m.color, borderColor: `${m.color}66`, background: `${m.color}1a` }}
    >
      <Icon className={size === 'lg' ? 'size-4' : 'size-3'} />
      {m.label}
      <span className='font-medium opacity-80'>· {alert && lane === 'RED' ? 'Safety alert' : m.action}</span>
    </span>
  )
}

export function UncertainBadge({ disagreement }: { disagreement?: number }) {
  return (
    <span
      className='inline-flex items-center gap-1 rounded-full border border-violet-500/40 bg-violet-500/10 px-2 py-0.5 text-[10px] font-semibold whitespace-nowrap text-violet-500 dark:text-violet-300'
      title='The glass-box and black-box models disagree strongly: human review, never released green'
    >
      <Scale className='size-3' /> Models disagree
      {disagreement != null && <span className='font-normal opacity-80'>Δ {pct(disagreement)}</span>}
    </span>
  )
}

/* ------------------------------------------------------------------ Numbers */
export function AnimatedNumber({
  value,
  format = (v: number) => num(Math.round(v)),
  className,
}: {
  value: number
  format?: (v: number) => string
  className?: string
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const prev = useRef(value)
  const fmt = useRef(format)
  useEffect(() => {
    fmt.current = format
  })
  useEffect(() => {
    const controls = animate(prev.current, value, {
      duration: 0.5,
      ease: 'easeOut',
      onUpdate: (v) => {
        if (ref.current) ref.current.textContent = fmt.current(v)
      },
    })
    prev.current = value
    return () => controls.stop()
  }, [value])
  return (
    <span ref={ref} className={cn('tabular-nums', className)}>
      {format(value)}
    </span>
  )
}

/* ------------------------------------------------------------------ Gauge */
export function Gauge({ value, label, sub, color }: { value: number; label: string; sub?: string; color: string }) {
  const r = 70
  const cx = 90
  const cy = 88
  const len = Math.PI * r
  const v = Math.max(0, Math.min(1, value))
  const arc = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`
  return (
    <div className='flex flex-col items-center'>
      <svg viewBox='0 0 180 104' className='w-full max-w-[210px]' role='img' aria-label={`${label}: ${(v * 100).toFixed(0)}%`}>
        <path d={arc} fill='none' className='stroke-muted' strokeWidth='14' strokeLinecap='round' />
        <motion.path
          d={arc}
          fill='none'
          stroke={color}
          strokeWidth='14'
          strokeLinecap='round'
          strokeDasharray={len}
          initial={{ strokeDashoffset: len }}
          animate={{ strokeDashoffset: len * (1 - v) }}
          transition={{ duration: 0.9, ease: 'easeOut' }}
        />
        <text x={cx} y={cy - 14} textAnchor='middle' className='fill-foreground' style={{ fontSize: 30, fontWeight: 650 }}>
          {(v * 100).toFixed(v < 0.1 ? 1 : 0)}%
        </text>
        <text x={cx} y={cy + 4} textAnchor='middle' className='fill-muted-foreground' style={{ fontSize: 10 }}>
          probability
        </text>
      </svg>
      <div className='-mt-1 text-center'>
        <div className='text-sm font-medium'>{label}</div>
        {sub && <div className='text-xs text-muted-foreground'>{sub}</div>}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ Reasons */
export function ReasonList({ reasons, compact = false }: { reasons: Reason[]; compact?: boolean }) {
  const money = useMoney()
  const max = Math.max(...reasons.map((r) => Math.abs(r.contribution)), 0.01)
  return (
    <ol className={cn('flex flex-col', compact ? 'gap-2' : 'gap-3')}>
      {reasons.map((r, i) => {
        const up = r.direction === 'raises'
        const color = up ? COLORS.red : COLORS.green
        const Icon = up ? ArrowUpRight : ArrowDownRight
        return (
          <motion.li
            key={`${r.group}-${i}`}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            className='rounded-lg border bg-muted/30 p-3'
          >
            <div className='flex items-center justify-between gap-3'>
              <div className='flex items-center gap-2 text-[11px] font-semibold tracking-wider uppercase' style={{ color }}>
                <Icon className='size-3.5' />
                {up ? 'Raises risk' : 'Lowers risk'} · {r.label}
              </div>
              <div className='flex h-1.5 w-28 overflow-hidden rounded-full bg-muted'>
                <div className='h-full rounded-full' style={{ background: color, width: `${(Math.abs(r.contribution) / max) * 100}%` }} />
              </div>
            </div>
            <p className={cn('mt-1.5 leading-snug', compact ? 'text-xs' : 'text-sm')}>{money.text(r.text)}</p>
          </motion.li>
        )
      })}
    </ol>
  )
}

/* ------------------------------------------------------------------ Waterfall */
export function WaterfallChart({ w, compact = false }: { w: Waterfall; compact?: boolean }) {
  const rows: { label: string; start: number; end: number; kind: 'base' | 'up' | 'down' | 'final' }[] = []
  rows.push({ label: 'Base rate (model start)', start: 0, end: w.base, kind: 'base' })
  let cur = w.base
  for (const s of w.steps) {
    rows.push({ label: s.label, start: cur, end: s.cumulative, kind: s.delta >= 0 ? 'up' : 'down' })
    cur = s.cumulative
  }
  if (Math.abs(w.other.delta) > 0.0005) {
    rows.push({ label: 'Other factors', start: cur, end: cur + w.other.delta, kind: w.other.delta >= 0 ? 'up' : 'down' })
  }
  rows.push({ label: 'Final probability', start: 0, end: w.final, kind: 'final' })
  const color = { base: '#64748b', up: COLORS.red, down: COLORS.green, final: COLORS.ai }
  return (
    <div className='flex flex-col gap-1.5'>
      {rows.map((r, i) => {
        const lo = Math.min(r.start, r.end)
        const width = Math.max(Math.abs(r.end - r.start), 0.003)
        const delta = r.end - r.start
        return (
          <div key={i} className={cn('grid items-center gap-3', compact ? 'grid-cols-[130px_1fr_64px]' : 'grid-cols-[180px_1fr_72px]')}>
            <div className={cn('truncate text-xs', r.kind === 'final' ? 'font-semibold' : 'text-muted-foreground')} title={r.label}>
              {r.label}
            </div>
            <div className='relative h-4 rounded bg-muted/50'>
              <motion.div
                className='absolute top-0 h-4 rounded'
                style={{ background: color[r.kind], left: `${lo * 100}%` }}
                initial={{ width: 0 }}
                animate={{ width: `${width * 100}%` }}
                transition={{ duration: 0.5, delay: i * 0.05 }}
              />
            </div>
            <div className='text-right text-xs tabular-nums'>
              {r.kind === 'base' || r.kind === 'final' ? pct(r.end, 1) : `${delta >= 0 ? '+' : '−'}${Math.abs(delta * 100).toFixed(1)} pts`}
            </div>
          </div>
        )
      })}
      <p className='mt-1 text-[11px] text-muted-foreground'>
        {w.model === 'ebm' ? 'Glass-box EBM' : 'LightGBM'}: exact additive decomposition (log-odds), shown as probability steps. Red raises,
        green lowers.
      </p>
    </div>
  )
}
