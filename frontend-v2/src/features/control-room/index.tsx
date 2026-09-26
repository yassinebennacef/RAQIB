import { useEffect, useMemo, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, Check, FastForward, Pause, Play, RotateCcw, Shuffle } from 'lucide-react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, apiV2, type PolicyKey, type StreamItemV2 } from '@/lib/api'
import { COLORS } from '@/lib/colors'
import { compact, num, pct, truncate } from '@/lib/format'
import { LANE_META } from '@/lib/lanes'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import {
  AnimatedNumber,
  Dot,
  ErrorState,
  InfoTip,
  LaneBadge,
  PageShell,
  RangeSlider,
  Segmented,
  Stat,
} from '@/components/raqib/kit'
import { MiniInspector } from '@/features/inspector/panel'

const LANE_ORDER = { RED: 0, YELLOW: 1, GREEN: 2 } as const
const FEED_MAX = 40
const tooltipStyle = { background: 'var(--popover)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }

function cumsum(a: number[] | undefined): number[] {
  const out: number[] = []
  let s = 0
  for (const v of a ?? []) {
    s += v
    out.push(s)
  }
  return out
}

export function ControlRoom() {
  const [capPct, setCapPct] = useState(5)
  const [explore, setExplore] = useState(false)
  const [speed, setSpeed] = useState(3)
  const [playing, setPlaying] = useState(false)
  const [day, setDay] = useState(-1)
  const [metric, setMetric] = useState<'frauds' | 'threats'>('frauds')
  const [openId, setOpenId] = useState<string | null>(null)

  const rate = capPct / 100
  const exp = explore ? 0.1 : 0
  const replay = useQuery({ queryKey: ['replay', rate, exp], queryFn: () => api.replay(rate, exp), placeholderData: keepPreviousData })
  const R = replay.data
  const nDays = R?.n_days ?? 91
  const started = day >= 0
  const d = Math.max(day, 0)
  const stream = useQuery({
    queryKey: ['stream', d, rate, exp],
    queryFn: () => apiV2.stream(d, rate, exp),
    placeholderData: keepPreviousData,
  })

  useEffect(() => {
    if (!playing) return
    const id = window.setInterval(() => setDay((x) => Math.min(x + 1, nDays - 1)), 1000 / speed)
    return () => window.clearInterval(id)
  }, [playing, speed, nDays])
  const atEnd = day >= nDays - 1
  const isPlaying = playing && !atEnd

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (e.code === 'Space' && tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'BUTTON') {
        e.preventDefault()
        setPlaying((p) => !p)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const aiKey: PolicyKey = explore ? 'ai_explore' : 'ai'
  const cum = useMemo(
    () => ({ n: cumsum(R?.n), threats: cumsum(R?.day_threats), green: cumsum(R?.policies[aiKey]?.green) }),
    [R, aiKey]
  )
  const at = (arr: number[] | undefined) => (started && arr ? (arr[d] ?? 0) : 0)
  const ai = R?.policies[aiKey]
  const aiF = at(ai?.cum_frauds)
  const ruleF = at(R?.policies.rule.cum_frauds)
  const rndF = at(R?.policies.random.cum_frauds)
  const aiT = at(ai?.cum_threats)
  const ruleT = at(R?.policies.rule.cum_threats)
  const rndT = at(R?.policies.random.cum_threats)
  const insp = at(ai?.cum_inspected)
  const declSoFar = at(cum.n)
  const threatsSoFar = at(cum.threats)
  const greenSoFar = at(cum.green)
  const gain = aiF - ruleF

  const cumKey = metric === 'frauds' ? 'cum_frauds' : 'cum_threats'
  const chartData = useMemo(() => {
    if (!R) return []
    return R.dates.map((date, i) => ({
      date: date.slice(5),
      ai: i <= day ? R.policies[aiKey][cumKey][i] : null,
      rule: i <= day ? R.policies.rule[cumKey][i] : null,
      random: i <= day ? R.policies.random[cumKey][i] : null,
    }))
  }, [R, day, aiKey, cumKey])
  const yMax = R ? Math.max(...(['ai', 'ai_explore', 'rule', 'random'] as PolicyKey[]).map((k) => R.policies[k][cumKey][R.policies[k][cumKey].length - 1] ?? 0), 1) : 10

  const items = useMemo(
    () => (stream.data?.items ?? []).slice().sort((a, b) => LANE_ORDER[a.lane] - LANE_ORDER[b.lane] || a.rank_in_day - b.rank_in_day),
    [stream.data]
  )
  const counts = useMemo(() => {
    const c = { RED: 0, YELLOW: 0, GREEN: 0 }
    for (const it of items) c[it.lane] += 1
    return c
  }, [items])

  if (replay.error && !R) return <ErrorState message={String(replay.error)} onRetry={() => replay.refetch()} />

  return (
    <PageShell
      title='Control room'
      why='Replay of 91 real test days: with the SAME daily inspection capacity, who catches more fraud and more public-safety threats?'
      actions={<Badge variant='outline' className='border-primary/40 text-primary'>Test period Apr–Jun 2021 · never seen in training</Badge>}
    >
      <Card className='flex-row flex-wrap items-center gap-x-8 gap-y-3 px-5 py-3'>
        <div className='flex min-w-[260px] flex-1 items-center gap-3'>
          <div className='w-32 shrink-0'>
            <div className='flex items-center gap-1 text-xs font-medium'>
              Inspection capacity
              <InfoTip text="Share of each day's declarations that can be physically inspected. AI, rule and random all get exactly the same number of inspections." />
            </div>
            <div className='text-lg font-semibold tabular-nums'>{capPct}% / day</div>
          </div>
          <RangeSlider value={capPct} min={1} max={20} onChange={setCapPct} label='Inspection capacity' />
        </div>
        <div className='flex items-center gap-3'>
          <Switch checked={explore} onCheckedChange={setExplore} aria-label='Exploration' />
          <div>
            <div className='flex items-center gap-1 text-xs font-medium'>
              <Shuffle className='size-3.5' /> Exploration 10%
              <InfoTip text='A small random share of the capacity is inspected at random so the system keeps learning about products and operators it would never pick.' />
            </div>
            <div className='text-[11px] text-muted-foreground'>{explore ? 'on: 10% of slots random' : 'off'}</div>
          </div>
        </div>
        <div className='flex w-56 items-center gap-3'>
          <div className='w-20 shrink-0 text-xs'>
            Speed
            <div className='text-sm font-semibold tabular-nums'>{speed} days/s</div>
          </div>
          <RangeSlider value={speed} min={1} max={8} onChange={setSpeed} label='Replay speed' />
        </div>
        <div className='flex items-center gap-2'>
          <Button onClick={() => setPlaying((p) => !p)} disabled={!R || atEnd} className='w-28'>
            {isPlaying ? <Pause /> : <Play />}
            {isPlaying ? 'Pause' : started ? 'Resume' : 'Play'}
          </Button>
          <Button variant='outline' size='icon' onClick={() => (setPlaying(false), setDay(-1))} aria-label='Reset' title='Reset'>
            <RotateCcw />
          </Button>
          <Button variant='outline' size='icon' onClick={() => (setPlaying(false), setDay(nDays - 1))} aria-label='Skip to the end' title='Skip to the end'>
            <FastForward />
          </Button>
        </div>
      </Card>

      <div className='grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5'>
        <Stat
          label='Day'
          value={
            <span>
              {started ? d + 1 : 0}
              <span className='text-base text-muted-foreground'> / {nDays}</span>
            </span>
          }
          sub={started && R ? R.dates[d] : 'press Play (or space)'}
        />
        <Stat label='Inspections so far' tip='Identical for every policy.' value={<AnimatedNumber value={insp} />} sub={`${capPct}% of ${num(declSoFar)} declarations`} />
        <Stat
          label='Hit rate'
          tip='Share of inspections that found a duty fraud (known after inspection).'
          value={<span className='text-ai'>{insp ? pct(aiF / insp) : '—'}</span>}
          sub={
            <span>
              rule <span style={{ color: COLORS.rule }}>{insp ? pct(ruleF / insp) : '—'}</span> · random {insp ? pct(rndF / insp) : '—'}
              {started && ruleF > 0 && <span className='ms-1 text-ai'>({gain >= 0 ? '+' : '−'}{pct(Math.abs(gain) / ruleF)} frauds)</span>}
            </span>
          }
        />
        <Stat
          label='Safety threats caught'
          tip='Critical frauds (serious violations, e.g. unsafe goods) caught, out of all threats present so far.'
          value={
            <span>
              <span className='text-ai'>{aiT}</span>
              <span className='text-base text-muted-foreground'> / {threatsSoFar}</span>
            </span>
          }
          sub={
            <span>
              rule <span style={{ color: COLORS.rule }}>{ruleT}</span> · random {rndT}
            </span>
          }
        />
        <Stat
          label='Released green'
          tip='Declarations sent to the green lane: no inspection, no document check. Declarations where the two models disagree are never released green.'
          value={<span className='text-lane-green'>{declSoFar ? pct(greenSoFar / declSoFar) : '—'}</span>}
          sub='faster clearance for compliant traders'
        />
      </div>

      <div className='grid grid-cols-1 gap-4 lg:grid-cols-12'>
        <Card className='gap-2 py-4 lg:col-span-4 2xl:col-span-3'>
          <CardHeader className='px-4'>
            <CardTitle>Today's declarations</CardTitle>
            <CardDescription>
              {stream.data ? `${stream.data.date} · ${num(stream.data.n)} declarations · ${stream.data.capacity} inspections` : 'Loading…'}
            </CardDescription>
            <div className='flex gap-1.5 text-[10px] tabular-nums'>
              {(['RED', 'YELLOW', 'GREEN'] as const).map((l) => (
                <span key={l} className='rounded px-1.5 py-0.5' style={{ color: LANE_META[l].color, background: `${LANE_META[l].color}14` }}>
                  {l} {counts[l]}
                </span>
              ))}
            </div>
          </CardHeader>
          <CardContent className='max-h-[560px] flex-1 overflow-y-auto px-2'>
            {!stream.data ? (
              <div className='flex flex-col gap-2 p-2'>
                {Array.from({ length: 8 }).map((_, i) => (
                  <Skeleton key={i} className='h-12' />
                ))}
              </div>
            ) : (
              <ul className='flex flex-col gap-0.5'>
                <AnimatePresence initial={false} mode='popLayout'>
                  {items.slice(0, FEED_MAX).map((it) => (
                    <FeedItem key={`${d}-${it.id}`} it={it} onOpen={() => setOpenId(it.id)} />
                  ))}
                </AnimatePresence>
                {items.length > FEED_MAX && (
                  <li className='px-3 py-2 text-center text-[11px] text-muted-foreground'>
                    + {num(items.length - FEED_MAX)} more low-risk declarations released green
                  </li>
                )}
              </ul>
            )}
          </CardContent>
          <div className='border-t px-4 pt-2 text-[10px] text-muted-foreground'>Click a declaration for the mini-inspector. Outcome icons are shown for the demo.</div>
        </Card>

        <div className='flex flex-col gap-4 lg:col-span-8 2xl:col-span-9'>
          <Card className='gap-4'>
            <CardHeader>
              <CardTitle>Same inspections, more fraud found</CardTitle>
              <CardDescription>{R ? `${num(R.totals.inspections)} inspections over ${R.n_days} days for every policy at ${capPct}% capacity` : '…'}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className='grid grid-cols-3 gap-4'>
                <RaceCounter label={explore ? 'RAQIB AI + explore' : 'RAQIB AI'} color={COLORS.aiLight} value={aiF} rate={insp ? aiF / insp : null} />
                <RaceCounter label='Current rule' hint='product history' color={COLORS.rule} value={ruleF} rate={insp ? ruleF / insp : null} />
                <RaceCounter label='Random' hint='no targeting' color={COLORS.random} value={rndF} rate={insp ? rndF / insp : null} />
              </div>
              <div className='mt-4 flex flex-wrap items-center gap-x-8 gap-y-2 rounded-lg border bg-muted/30 px-4 py-3'>
                <div className='flex items-center gap-2 text-xs font-medium tracking-wider text-muted-foreground uppercase'>
                  <AlertTriangle className='size-4 text-lane-red' /> Public-safety threats caught
                </div>
                <div className='flex items-baseline gap-2'>
                  <AnimatedNumber value={aiT} className='text-3xl font-bold text-ai' />
                  <span className='text-xs text-muted-foreground'>AI</span>
                </div>
                <div className='flex items-baseline gap-2'>
                  <AnimatedNumber value={ruleT} className='text-3xl font-bold' />
                  <span className='text-xs' style={{ color: COLORS.rule }}>
                    rule
                  </span>
                </div>
                <div className='flex items-baseline gap-2'>
                  <AnimatedNumber value={rndT} className='text-2xl font-semibold text-muted-foreground' />
                  <span className='text-xs text-muted-foreground'>random</span>
                </div>
                <div className='ms-auto text-xs text-muted-foreground'>of {num(threatsSoFar)} threats present so far</div>
              </div>
            </CardContent>
          </Card>

          <Card className='gap-2'>
            <CardHeader className='flex flex-row items-start justify-between gap-3'>
              <div>
                <CardTitle>Cumulative {metric === 'frauds' ? 'frauds' : 'public-safety threats'} caught</CardTitle>
                <CardDescription>Day by day over the test period · identical capacity</CardDescription>
              </div>
              <div className='flex items-center gap-4'>
                <div className='hidden items-center gap-3 text-xs text-muted-foreground md:flex'>
                  <span className='flex items-center gap-1.5'><Dot color={COLORS.ai} />AI</span>
                  <span className='flex items-center gap-1.5'><Dot color={COLORS.rule} />Rule</span>
                  <span className='flex items-center gap-1.5'><Dot color={COLORS.random} />Random</span>
                </div>
                <Segmented value={metric} onChange={setMetric} options={[{ value: 'frauds', label: 'Frauds' }, { value: 'threats', label: 'Threats' }]} />
              </div>
            </CardHeader>
            <CardContent className='h-[300px]'>
              {!R ? (
                <Skeleton className='h-full' />
              ) : (
                <ResponsiveContainer width='100%' height='100%'>
                  <LineChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
                    <CartesianGrid strokeDasharray='3 3' vertical={false} />
                    <XAxis dataKey='date' tick={{ fontSize: 11 }} interval={6} tickLine={false} />
                    <YAxis domain={[0, Math.ceil(yMax * 1.05)]} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} allowDecimals={false} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Line type='monotone' dataKey='random' name='Random' stroke={COLORS.random} strokeWidth={2} dot={false} isAnimationActive={false} />
                    <Line type='monotone' dataKey='rule' name='Rule' stroke={COLORS.rule} strokeWidth={2.5} dot={false} isAnimationActive={false} />
                    <Line type='monotone' dataKey='ai' name='AI' stroke={COLORS.ai} strokeWidth={3} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <Sheet open={openId != null} onOpenChange={(o) => !o && setOpenId(null)}>
        <SheetContent className='w-full overflow-y-auto sm:max-w-xl'>
          <SheetHeader>
            <SheetTitle>Declaration {openId}</SheetTitle>
            <SheetDescription>Mini-inspector · advisory score, the officer decides</SheetDescription>
          </SheetHeader>
          <div className='px-4 pb-6'>{openId && <MiniInspector id={openId} rate={rate} explore={exp} />}</div>
        </SheetContent>
      </Sheet>
    </PageShell>
  )
}

function RaceCounter({ label, hint, color, value, rate }: { label: string; hint?: string; color: string; value: number; rate: number | null }) {
  return (
    <div className='rounded-xl border bg-muted/30 px-4 py-3'>
      <div className='flex items-center gap-2 truncate text-[11px] font-semibold tracking-wider uppercase' style={{ color }}>
        <Dot color={color} /> {label}
        {hint && <span className='hidden font-normal tracking-normal text-muted-foreground normal-case xl:inline'>· {hint}</span>}
      </div>
      <AnimatedNumber value={value} className='mt-1 block text-5xl leading-none font-bold xl:text-6xl' />
      <div className='mt-1.5 text-xs text-muted-foreground'>
        frauds caught · hit rate <span className='tabular-nums'>{rate == null ? '—' : pct(rate)}</span>
      </div>
    </div>
  )
}

function FeedItem({ it, onOpen }: { it: StreamItemV2; onOpen: () => void }) {
  const color = LANE_META[it.lane].color
  return (
    <motion.li layout='position' initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
      <button
        onClick={onOpen}
        className='group flex w-full items-center gap-3 rounded-lg border border-transparent px-2.5 py-2 text-start transition-colors hover:border-border hover:bg-accent'
      >
        <span className='h-9 w-1 shrink-0 rounded-full' style={{ background: color }} />
        <div className='min-w-0 flex-1'>
          <div className='truncate text-[13px]' title={it.hs_desc}>
            {truncate(it.hs_desc, 70)}
          </div>
          <div className='mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground'>
            <span className='font-mono'>{it.hs6}</span>·<span>{it.origin}</span>·<span className='tabular-nums'>{compact(it.item_price)} KRW</span>
            {it.rule_selected && (
              <span className='rounded px-1 text-[9px] font-semibold' style={{ color: COLORS.rule, background: `${COLORS.rule}1f` }} title='The current rule would inspect this one'>
                RULE
              </span>
            )}
            {it.uncertain && <span className='rounded bg-violet-500/15 px-1 text-[9px] font-semibold text-violet-500 dark:text-violet-300' title='Models disagree: human review'>REVIEW</span>}
            {it.explored && <span className='rounded bg-muted px-1 text-[9px] font-semibold'>EXPLORE</span>}
          </div>
        </div>
        <div className='flex shrink-0 flex-col items-end gap-1'>
          <LaneBadge lane={it.lane} alert={it.alert} />
          <span className={cn('flex items-center gap-1 text-[10px] tabular-nums text-muted-foreground')}>
            {it.lane === 'RED' &&
              (it.truth.fraud || it.truth.critical ? (
                <span className='flex items-center gap-0.5 text-lane-red'>
                  <Check className='size-3' /> found
                </span>
              ) : (
                <span>clean</span>
              ))}
            <span>risk {pct(it.p_fraud)}</span>
          </span>
        </div>
      </button>
    </motion.li>
  )
}
