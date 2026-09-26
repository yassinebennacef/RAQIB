import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Clock, ShieldAlert, TrendingDown } from 'lucide-react'
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { apiV2 } from '@/lib/api'
import { COLORS } from '@/lib/colors'
import { num, pct } from '@/lib/format'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState, InfoTip, PageShell, RangeSlider, Segmented } from '@/components/raqib/kit'

const tooltipStyle = { background: 'var(--popover)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }

export function Impact() {
  const [minutes, setMinutes] = useState(60)
  const [ratePct, setRatePct] = useState(5)
  const [metric, setMetric] = useState<'frauds' | 'threats'>('frauds')
  const q = useQuery({ queryKey: ['efficiency', minutes], queryFn: () => apiV2.efficiency(minutes), placeholderData: keepPreviousData })
  const e = q.data

  if (q.error && !e) return <ErrorState message={String(q.error)} onRetry={() => q.refetch()} />
  const point = e?.curve.find((c) => Math.round(c.rate * 100) === ratePct)
  const data = e?.curve.map((c) => ({ rate: Math.round(c.rate * 100), ai: c.ai[metric], rule: c.rule[metric], random: c.random[metric], insp: c.inspections }))
  const mt = e?.matching
  const pl = e?.pooled
  const oh = e?.officer_hours

  return (
    <PageShell
      title='Impact simulator'
      why='The same results with fewer inspections: officers freed for the cases that matter, honest traders cleared faster.'
      actions={<Badge variant='outline'>Daily replay of the 91-day test period · no exploration</Badge>}
    >
      <div className='grid grid-cols-1 gap-4 lg:grid-cols-3'>
        <Card className='gap-2 border-primary/40 bg-primary/5'>
          <CardHeader>
            <CardDescription className='flex items-center gap-2'>
              <TrendingDown className='size-4 text-primary' /> Same frauds, fewer inspections (daily)
            </CardDescription>
            <CardTitle className='text-4xl text-primary tabular-nums'>{mt ? `−${pct(mt.fewer_pct)}` : <Skeleton className='h-10 w-32' />}</CardTitle>
          </CardHeader>
          <CardContent className='text-sm text-muted-foreground'>
            {mt && (
              <>
                The rule needs <b className='text-foreground'>{num(mt.reference.inspections)}</b> inspections (5% a day) to catch{' '}
                <b className='text-foreground'>{num(mt.reference.frauds)}</b> frauds. RAQIB catches <b className='text-foreground'>{num(mt.ai_frauds)}</b> with{' '}
                <b className='text-foreground'>{num(mt.ai_inspections)}</b> ({pct(mt.ai_rate, 1)} a day).
              </>
            )}
          </CardContent>
        </Card>
        <Card className='gap-2'>
          <CardHeader>
            <CardDescription className='flex items-center gap-2'>
              <TrendingDown className='size-4' /> Pooled ranking of the whole period
              <InfoTip text='One ranking of all test declarations instead of day by day: how many inspections does the AI need to find as many frauds as the rule with its top 5%?' />
            </CardDescription>
            <CardTitle className='text-4xl tabular-nums'>{pl ? `−${pct(pl.fewer_pct)}` : <Skeleton className='h-10 w-32' />}</CardTitle>
          </CardHeader>
          <CardContent className='text-sm text-muted-foreground'>
            {pl && (
              <>
                {num(pl.k_ai_needed)} AI inspections find the {num(pl.rule_frauds)} frauds the rule finds with {num(pl.k_rule)}.
              </>
            )}
          </CardContent>
        </Card>
        <Card className='gap-2'>
          <CardHeader>
            <CardDescription className='flex items-center gap-2'>
              <Clock className='size-4' /> Officer hours freed
              <Badge variant='outline' className='border-lane-yellow/50 text-lane-yellow'>
                assumption
              </Badge>
            </CardDescription>
            <CardTitle className='text-4xl tabular-nums'>{oh ? `${num(oh.hours_freed_per_year)} h/yr` : <Skeleton className='h-10 w-32' />}</CardTitle>
          </CardHeader>
          <CardContent className='flex flex-col gap-2 text-sm text-muted-foreground'>
            {oh && (
              <span>
                {num(mt?.fewer_inspections ?? 0)} fewer inspections over {oh.test_days} days × {oh.minutes_per_inspection} min = {num(oh.hours_freed_test_period)} h, scaled to a year.
              </span>
            )}
            <label className='flex items-center gap-2 text-xs'>
              Minutes per physical inspection
              <Input
                type='number'
                min={5}
                max={600}
                value={minutes}
                onChange={(ev) => setMinutes(Math.max(5, Math.min(600, Number(ev.target.value) || 60)))}
                className='h-8 w-20'
              />
            </label>
          </CardContent>
        </Card>
      </div>

      <div className='grid grid-cols-1 gap-4 xl:grid-cols-12'>
        <Card className='gap-2 xl:col-span-8'>
          <CardHeader className='flex flex-row items-start justify-between gap-3'>
            <div>
              <CardTitle>Capacity curve</CardTitle>
              <CardDescription>{metric === 'frauds' ? 'Frauds' : 'Public-safety threats'} caught over the test period for each daily inspection capacity</CardDescription>
            </div>
            <Segmented value={metric} onChange={setMetric} options={[{ value: 'frauds', label: 'Frauds' }, { value: 'threats', label: 'Threats' }]} />
          </CardHeader>
          <CardContent className='h-[340px]'>
            {!data ? (
              <Skeleton className='h-full' />
            ) : (
              <ResponsiveContainer width='100%' height='100%'>
                <LineChart data={data} margin={{ top: 8, right: 16, left: -4, bottom: 12 }}>
                  <CartesianGrid strokeDasharray='3 3' />
                  <XAxis dataKey='rate' tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} label={{ value: 'daily inspection capacity', position: 'insideBottom', offset: -6, fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip contentStyle={tooltipStyle} labelFormatter={(v) => `${v}% capacity`} />
                  <Legend wrapperStyle={{ fontSize: 12 }} verticalAlign='top' />
                  <ReferenceLine x={ratePct} stroke='var(--muted-foreground)' strokeDasharray='4 4' />
                  <Line dataKey='ai' name='RAQIB AI' stroke={COLORS.ai} strokeWidth={3} dot={{ r: 2 }} />
                  <Line dataKey='rule' name='Current rule' stroke={COLORS.rule} strokeWidth={2.5} dot={{ r: 2 }} />
                  <Line dataKey='random' name='Random' stroke={COLORS.random} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
        <Card className='gap-4 xl:col-span-4'>
          <CardHeader>
            <CardTitle>At a given capacity</CardTitle>
            <CardDescription>Move the slider: same number of inspections for every policy</CardDescription>
          </CardHeader>
          <CardContent className='flex flex-col gap-4'>
            <div className='flex items-center gap-3'>
              <span className='w-20 text-lg font-semibold tabular-nums'>{ratePct}% / day</span>
              <RangeSlider value={ratePct} min={1} max={20} onChange={setRatePct} label='Capacity' />
            </div>
            {point ? (
              <div className='flex flex-col gap-2 text-sm'>
                <div className='text-xs text-muted-foreground'>{num(point.inspections)} inspections over the period</div>
                {(
                  [
                    ['RAQIB AI', point.ai, COLORS.ai],
                    ['Current rule', point.rule, COLORS.rule],
                    ['Random', point.random, COLORS.random],
                  ] as const
                ).map(([label, v, color]) => (
                  <div key={label} className='flex items-center justify-between rounded-lg border bg-muted/30 px-3 py-2'>
                    <span style={{ color }} className='font-medium'>
                      {label}
                    </span>
                    <span className='tabular-nums'>
                      <b>{num(v.frauds)}</b> frauds · <b>{num(v.threats)}</b> threats · hit {pct(v.frauds / Math.max(point.inspections, 1))}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <Skeleton className='h-32' />
            )}
            {e && (
              <div className='flex items-start gap-2 rounded-lg border border-lane-red/30 bg-lane-red/5 p-3 text-xs'>
                <ShieldAlert className='mt-0.5 size-4 shrink-0 text-lane-red' />
                <span>
                  Public safety: the rule at 5% catches <b>{e.threats.rule_at_ref}</b> threats; RAQIB already catches at least as many at{' '}
                  <b>{e.threats.ai_rate_matching_threats != null ? pct(e.threats.ai_rate_matching_threats, 1) : '—'}</b> capacity (
                  {num(e.threats.ai_inspections ?? 0)} inspections).
                </span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </PageShell>
  )
}
