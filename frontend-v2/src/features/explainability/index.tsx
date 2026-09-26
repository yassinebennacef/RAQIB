import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, Search, XCircle } from 'lucide-react'
import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { apiV2, type Experiment, type TargetKey, type XaiTarget } from '@/lib/api'
import { useMoney } from '@/lib/currency'
import { COLORS } from '@/lib/colors'
import { compact, dec, num, pct, pts } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState, LaneBadge, PageShell, ReasonList, Segmented, UncertainBadge, WaterfallChart } from '@/components/raqib/kit'
import { useDeclaration } from '@/features/inspector/panel'
import { WhatIfPanel } from './whatif'

const tooltipStyle = { background: 'var(--popover)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }

function fmtX(x: number, scale: 'linear' | 'log') {
  return scale === 'log' ? compact(x) : x.toFixed(x < 10 ? 1 : 0)
}

function ShapeCard({ s }: { s: XaiTarget['shapes'][number] }) {
  const money = useMoney()
  const isKrw = s.x_label.includes('KRW')
  const xLabel = isKrw ? s.x_label.replace('KRW', money.label) : s.x_label
  const cx = (v: number) => (isKrw ? money.fromKrw(v) : v)
  const data = s.points.map((p) => ({ x: s.x_scale === 'log' ? Math.log10(Math.max(p.x, 1e-3)) : p.x, raw: p.x, y: p.y, band: [p.lower, p.upper] }))
  return (
    <div className='rounded-lg border bg-muted/20 p-3'>
      <div className='text-xs font-medium'>{s.label}</div>
      <div className='h-36'>
        <ResponsiveContainer width='100%' height='100%'>
          <ComposedChart data={data} margin={{ top: 6, right: 6, left: -26, bottom: 0 }}>
            <CartesianGrid strokeDasharray='3 3' />
            <XAxis
              dataKey='x'
              type='number'
              domain={['dataMin', 'dataMax']}
              tick={{ fontSize: 9 }}
              tickFormatter={(v) => fmtX(cx(s.x_scale === 'log' ? 10 ** v : v), s.x_scale)}
            />
            <YAxis tick={{ fontSize: 9 }} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelFormatter={(v) => `${xLabel}: ${fmtX(cx(s.x_scale === 'log' ? 10 ** Number(v) : Number(v)), s.x_scale)}`}
              formatter={(v, n) => (n === 'y' ? [dec(Number(v), 2), 'effect (log-odds)'] : [null, null])}
            />
            <Area dataKey='band' stroke='none' fill={COLORS.ebm} fillOpacity={0.15} isAnimationActive={false} />
            <Line dataKey='y' stroke={COLORS.ebm} strokeWidth={2} dot={false} type='stepAfter' isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className='text-[10px] text-muted-foreground'>
        x: {xLabel}
        {s.x_scale === 'log' ? ' (log scale)' : ''} · y: effect on risk (log-odds; above 0 raises risk)
      </div>
    </div>
  )
}

function ExperimentCard({ e }: { e: Experiment }) {
  const kept = e.decision === 'kept'
  const r = e.result as Record<string, number>
  const measured =
    e.key === 'isolation_forest'
      ? `Fraud AUC ${dec(r.fraud_auc, 3)} · top-1% fraud rate ${pct(r.top1_fraud_rate, 1)} vs base ${pct(r.base_rate, 1)}`
      : e.key === 'network_2hop'
        ? `AUC ${dec(r.auc_with, 4)} with vs ${dec(r.auc_without, 4)} without · P@5% ${pct(r.p5_with, 1)} vs ${pct(r.p5_without, 1)}`
        : e.key === 'ebm'
          ? `Fraud AUC ${dec(r.fraud_auc, 3)} · P@5% ${pct(r.fraud_precision_at_5, 1)} (LightGBM ${dec(e.baseline?.fraud_auc ?? 0, 3)} · ${pct(e.baseline?.fraud_precision_at_5 ?? 0, 1)})`
          : `${num(r.n_flagged)} flagged (${pct(r.share_flagged, 1)}) · fraud rate ${pct(r.fraud_rate_flagged ?? 0)} vs ${pct(r.fraud_rate_all)}`
  return (
    <Card className={cn('gap-2', kept ? 'border-lane-green/40' : 'border-lane-red/40')}>
      <CardHeader>
        <CardTitle className='flex items-center gap-2 text-sm'>
          {kept ? <CheckCircle2 className='size-4 text-lane-green' /> : <XCircle className='size-4 text-lane-red' />}
          {e.title}
          <Badge variant='outline' className={kept ? 'text-lane-green' : 'text-lane-red'}>
            {e.decision}
          </Badge>
        </CardTitle>
        <CardDescription className='text-xs'>{e.hypothesis}</CardDescription>
      </CardHeader>
      <CardContent className='flex flex-col gap-1.5 text-xs'>
        <div className='font-medium tabular-nums'>{measured}</div>
        <div className='text-muted-foreground'>{e.method}</div>
        <div>{e.reason}</div>
      </CardContent>
    </Card>
  )
}

export function Explainability() {
  const [target, setTarget] = useState<TargetKey>('fraud')
  const xai = useQuery({ queryKey: ['xai'], queryFn: apiV2.xaiGlobal })
  const m = useQuery({ queryKey: ['metrics-v2'], queryFn: apiV2.metrics })
  const ex = useQuery({ queryKey: ['experiments'], queryFn: apiV2.experiments })
  const top = useQuery({ queryKey: ['worklist-top'], queryFn: () => apiV2.worklist({ lane: 'RED', uncertain: false, page_size: 30 }) })
  const [idText, setIdText] = useState('')
  const [id, setId] = useState<string | null>(null)
  const solid = top.data?.items.find((it) => !it.top_reason.includes('thin history') && it.top_reason.startsWith('Product'))
  const current = id ?? solid?.id ?? top.data?.items[0]?.id ?? null
  const decl = useDeclaration(current ?? '', 0.05, 0)
  const d = current ? decl.data : undefined

  if (xai.error) return <ErrorState message={String(xai.error)} onRetry={() => xai.refetch()} />
  const X = xai.data?.targets[target]
  const imp = (X?.importances ?? []).slice(0, 12).map((r) => ({ label: r.label.length > 44 ? `${r.label.slice(0, 43)}…` : r.label, share: r.share, inter: r.group === 'interaction' }))
  const M = m.data

  return (
    <PageShell
      title='Explainability'
      why='A glass box: every lane is an exact sum of readable contributions, and the transparent model is as accurate as the black box.'
      actions={
        <Segmented
          value={target}
          onChange={setTarget}
          options={[
            { value: 'fraud', label: 'Duty fraud' },
            { value: 'critical', label: 'Public safety' },
          ]}
        />
      }
    >
      {/* (d) glass box vs black box */}
      <Card className='gap-3'>
        <CardHeader>
          <CardTitle>Glass box vs black box</CardTitle>
          <CardDescription>{M ? M.primary_model.rule : 'Loading…'}</CardDescription>
        </CardHeader>
        <CardContent>
          {!M ? (
            <Skeleton className='h-24' />
          ) : (
            <div className='grid grid-cols-1 gap-3 md:grid-cols-2'>
              {(['fraud', 'critical'] as const).map((t) => {
                const T = M.targets[t]
                const key = t === 'fraud' ? 'precision_at_5' : 'recall_at_5'
                const g = T.ebm_vs_lightgbm
                return (
                  <div key={t} className='rounded-lg border bg-muted/20 p-3 text-sm'>
                    <div className='mb-2 flex items-center justify-between'>
                      <span className='font-medium'>{t === 'fraud' ? 'Duty fraud · precision @5%' : 'Public safety · recall @5%'}</span>
                      <Badge variant='outline'>primary: {M.primary_model[t] === 'ebm' ? 'EBM (glass box)' : 'LightGBM'}</Badge>
                    </div>
                    <div className='grid grid-cols-2 gap-2 tabular-nums'>
                      <div>
                        <div className='text-xs' style={{ color: COLORS.ebm }}>
                          EBM (glass box)
                        </div>
                        <div className='text-2xl font-semibold'>{pct(T.methods.ebm[key], 1)}</div>
                        <div className='text-xs text-muted-foreground'>AUC {dec(T.methods.ebm.auc, 3)}</div>
                      </div>
                      <div>
                        <div className='text-xs text-ai'>LightGBM (black box)</div>
                        <div className='text-2xl font-semibold'>{pct(T.methods.lightgbm[key], 1)}</div>
                        <div className='text-xs text-muted-foreground'>AUC {dec(T.methods.lightgbm.auc, 3)}</div>
                      </div>
                    </div>
                    <div className='mt-2 text-xs text-muted-foreground'>
                      EBM − LightGBM: {pts(g.mean_gain)} (95% CI {pts(g.ci95[0])} to {pts(g.ci95[1])})
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* (a) what the model learned */}
      <div className='grid grid-cols-1 gap-4 xl:grid-cols-12'>
        <Card className='gap-2 xl:col-span-5'>
          <CardHeader>
            <CardTitle>What the glass-box model relies on</CardTitle>
            <CardDescription>Mean absolute contribution of each term (share); purple = pairwise interaction</CardDescription>
          </CardHeader>
          <CardContent className='h-[420px]'>
            {!X ? (
              <Skeleton className='h-full' />
            ) : (
              <ResponsiveContainer width='100%' height='100%'>
                <BarChart data={imp} layout='vertical' margin={{ top: 0, right: 12, left: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray='3 3' horizontal={false} />
                  <XAxis type='number' tickFormatter={(v) => pct(v)} tick={{ fontSize: 10 }} />
                  <YAxis type='category' dataKey='label' tick={{ fontSize: 10 }} width={210} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(v) => pct(Number(v), 1)} />
                  <Bar dataKey='share' radius={[0, 4, 4, 0]} fill={COLORS.ebm} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
        <Card className='gap-2 xl:col-span-7'>
          <CardHeader>
            <CardTitle>What the model learned — shape functions</CardTitle>
            <CardDescription>How each factor moves the risk, exactly as the model uses it (band = spread across bags)</CardDescription>
          </CardHeader>
          <CardContent className='grid grid-cols-1 gap-3 sm:grid-cols-2'>
            {!X ? Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className='h-44' />) : X.shapes.slice(0, 6).map((s) => <ShapeCard key={s.term} s={s} />)}
          </CardContent>
        </Card>
      </div>

      {/* (b) local waterfall */}
      <Card className='gap-3'>
        <CardHeader className='flex flex-row flex-wrap items-start justify-between gap-3'>
          <div>
            <CardTitle>One declaration, exactly explained</CardTitle>
            <CardDescription>Base rate → each factor → final probability (duty fraud, primary model)</CardDescription>
          </div>
          <form
            className='flex items-center gap-2'
            onSubmit={(ev) => {
              ev.preventDefault()
              if (idText.trim()) setId(idText.trim())
            }}
          >
            <Input value={idText} onChange={(ev) => setIdText(ev.target.value)} placeholder='Declaration ID' className='h-8 w-40 font-mono' />
            <Button size='sm' type='submit'>
              <Search /> Explain
            </Button>
          </form>
        </CardHeader>
        <CardContent>
          {decl.error ? (
            <p className='text-sm text-muted-foreground'>Declaration not found in the test period.</p>
          ) : !d ? (
            <Skeleton className='h-56' />
          ) : (
            <div className='grid grid-cols-1 gap-6 lg:grid-cols-2'>
              <div className='flex flex-col gap-3'>
                <div className='flex flex-wrap items-center gap-2'>
                  <span className='font-mono text-sm'>{d.declaration.id}</span>
                  <LaneBadge lane={d.ai.lane} alert={d.ai.alert} />
                  {d.ai.uncertain && <UncertainBadge disagreement={d.ai.disagreement} />}
                </div>
                <p className='text-sm text-muted-foreground'>
                  <span className='font-mono'>{d.declaration.hs6}</span> · {d.declaration.hs_desc}
                </p>
                <WaterfallChart w={d.waterfall} />
              </div>
              <ReasonList reasons={d.ai.reasons_fraud} compact />
            </div>
          )}
        </CardContent>
      </Card>

      {/* (c) what-if */}
      {d && (
        <WhatIfPanel
          key={d.declaration.id}
          declarationId={d.declaration.id}
          base={{ item_price: d.declaration.item_price, net_mass: d.declaration.net_mass, tax_rate: d.declaration.tax_rate }}
        />
      )}

      {/* (e) tested and rejected */}
      <div>
        <h2 className='mb-1 text-lg font-semibold'>Tested ideas — we only ship what we measure</h2>
        <p className='mb-3 text-sm text-muted-foreground'>Four ideas measured on the same test period: two kept, two rejected.</p>
        <div className='grid grid-cols-1 gap-3 md:grid-cols-2'>
          {ex.data ? ex.data.experiments.map((e) => <ExperimentCard key={e.key} e={e} />) : Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className='h-40' />)}
        </div>
      </div>
    </PageShell>
  )
}
