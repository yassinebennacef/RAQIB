import { useEffect, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowRight, FlaskConical } from 'lucide-react'
import { apiV2, type DeclarationInput, type WhatIfChanges } from '@/lib/api'
import { COLORS } from '@/lib/colors'
import { useMoney } from '@/lib/currency'
import { compact, pct } from '@/lib/format'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Skeleton } from '@/components/ui/skeleton'
import { LaneBadge, RangeSlider, UncertainBadge, WaterfallChart } from '@/components/raqib/kit'

type Base = { item_price: number; net_mass: number; tax_rate: number }

function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const id = window.setTimeout(() => setV(value), ms)
    return () => window.clearTimeout(id)
  }, [value, ms])
  return v
}

const FACTORS = [0.1, 0.2, 0.3, 0.5, 0.7, 1, 1.5, 2, 3, 5, 10]

export function WhatIfPanel({ declarationId, declaration, base }: { declarationId?: string; declaration?: DeclarationInput; base: Base }) {
  const [valueIdx, setValueIdx] = useState(5)
  const [massIdx, setMassIdx] = useState(5)
  const [tax, setTax] = useState(base.tax_rate)
  const [newOps, setNewOps] = useState({ importer: false, declarant: false, seller: false })
  const money = useMoney()

  const changes: WhatIfChanges = {}
  if (valueIdx !== 5) changes.item_price = Math.round(base.item_price * FACTORS[valueIdx] * 100) / 100
  if (massIdx !== 5) changes.net_mass = Math.round(base.net_mass * FACTORS[massIdx] * 100) / 100
  if (tax !== base.tax_rate) changes.tax_rate = tax
  for (const k of ['importer', 'declarant', 'seller'] as const) if (newOps[k]) changes[k] = 'new'
  const body = useDebounced({ declaration_id: declarationId, declaration, changes })
  const q = useQuery({
    queryKey: ['whatif', body],
    queryFn: () => apiV2.whatif(body),
    placeholderData: keepPreviousData,
  })
  const r = q.data

  return (
    <Card className='gap-4'>
      <CardHeader>
        <CardTitle className='flex items-center gap-2'>
          <FlaskConical className='size-4' /> What-if simulator
          <Badge variant='outline'>officer-only</Badge>
        </CardTitle>
        <CardDescription>Change the declaration and see the risk, the lane and the exact contributions move live. Never shown to traders.</CardDescription>
      </CardHeader>
      <CardContent className='grid grid-cols-1 gap-6 lg:grid-cols-5'>
        <div className='flex flex-col gap-4 lg:col-span-2'>
          <label className='flex flex-col gap-2 text-xs'>
            <span className='flex justify-between'>
              Declared value <b className='tabular-nums'>×{FACTORS[valueIdx]} · {money.krw(base.item_price * FACTORS[valueIdx])}</b>
            </span>
            <RangeSlider value={valueIdx} min={0} max={FACTORS.length - 1} onChange={setValueIdx} label='Declared value factor' />
          </label>
          <label className='flex flex-col gap-2 text-xs'>
            <span className='flex justify-between'>
              Net mass <b className='tabular-nums'>×{FACTORS[massIdx]} · {compact(base.net_mass * FACTORS[massIdx])} kg</b>
            </span>
            <RangeSlider value={massIdx} min={0} max={FACTORS.length - 1} onChange={setMassIdx} label='Net mass factor' />
          </label>
          <label className='flex flex-col gap-2 text-xs'>
            <span className='flex justify-between'>
              Tax rate <b className='tabular-nums'>{tax}%</b>
            </span>
            <RangeSlider value={tax} min={0} max={30} step={0.5} onChange={setTax} label='Tax rate' />
          </label>
          <div className='flex flex-col gap-2 text-xs'>
            <span className='text-muted-foreground'>Replace an operator by a new one (no history)</span>
            {(['importer', 'declarant', 'seller'] as const).map((k) => (
              <label key={k} className='flex items-center gap-2'>
                <Checkbox checked={newOps[k]} onCheckedChange={(v) => setNewOps((o) => ({ ...o, [k]: !!v }))} /> new {k}
              </label>
            ))}
          </div>
        </div>
        <div className='flex flex-col gap-4 lg:col-span-3'>
          {!r ? (
            <Skeleton className='h-64' />
          ) : (
            <>
              <div className='flex flex-wrap items-center gap-4 rounded-lg border bg-muted/30 p-3'>
                <div className='flex flex-col items-start gap-1'>
                  <span className='text-[11px] text-muted-foreground uppercase'>Before</span>
                  <span className='text-2xl font-semibold tabular-nums'>{pct(r.before.p_fraud)}</span>
                  <LaneBadge lane={r.before.lane} alert={r.before.alert} />
                </div>
                <ArrowRight className='size-5 text-muted-foreground' />
                <div className='flex flex-col items-start gap-1'>
                  <span className='text-[11px] text-muted-foreground uppercase'>After</span>
                  <span
                    className='text-2xl font-semibold tabular-nums'
                    style={{ color: r.after.p_fraud > r.before.p_fraud + 0.005 ? COLORS.red : r.after.p_fraud < r.before.p_fraud - 0.005 ? COLORS.green : undefined }}
                  >
                    {pct(r.after.p_fraud)}
                  </span>
                  <LaneBadge lane={r.after.lane} alert={r.after.alert} />
                </div>
                {r.after.uncertain && <UncertainBadge disagreement={r.after.disagreement} />}
                <div className='ms-auto max-w-56 text-xs text-muted-foreground'>{r.after.lane_reason}</div>
              </div>
              {r.deltas.length > 0 && (
                <div className='flex flex-wrap gap-2 text-xs'>
                  {r.deltas.slice(0, 5).map((dl) => (
                    <span key={dl.group} className='rounded-md border px-2 py-1' style={{ color: dl.delta > 0 ? COLORS.red : COLORS.green }}>
                      {dl.label} {dl.delta > 0 ? '+' : '−'}
                      {Math.abs(dl.delta).toFixed(2)} log-odds
                    </span>
                  ))}
                </div>
              )}
              <WaterfallChart w={r.after.waterfall} compact />
            </>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
