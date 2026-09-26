import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { motion } from 'framer-motion'
import { Eye, FileSearch, Gavel, Hash, ShieldAlert, ShieldCheck, UserRound } from 'lucide-react'
import { toast } from 'sonner'
import { api, apiV2, type DeclarationDetailV2, type DecisionEntry, type OperatorHistory } from '@/lib/api'
import { COLORS } from '@/lib/colors'
import { compact, num, pct, pctile, shortHash } from '@/lib/format'
import { LANE_META } from '@/lib/lanes'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState, Gauge, InfoTip, LaneBadge, ReasonList, UncertainBadge, WaterfallChart } from '@/components/raqib/kit'
import { NetworkGraph } from '@/components/raqib/network-graph'
import { OfficerBrief } from '@/components/raqib/llm'

export function useDeclaration(id: string, rate = 0.05, explore = 0) {
  return useQuery({ queryKey: ['declaration', id, rate, explore], queryFn: () => apiV2.declaration(id, rate, explore), enabled: id !== '' })
}

function readOfficer() {
  try {
    return window.localStorage.getItem('raqib-officer') || 'Agent · Office 30'
  } catch {
    return 'Agent · Office 30'
  }
}

export function DecisionPanel({ d }: { d: DeclarationDetailV2 }) {
  const qc = useQueryClient()
  const [officer, setOfficer] = useState(readOfficer)
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  const [reveal, setReveal] = useState(false)
  const id = d.declaration.id

  async function decide(decision: DecisionEntry['decision']) {
    setBusy(true)
    try {
      try {
        window.localStorage.setItem('raqib-officer', officer)
      } catch {
        /* storage unavailable */
      }
      const res = await api.decide({ declaration_id: id, decision, comment, officer })
      toast.success(`Decision logged: ${decision.replace('_', ' ')}`, {
        description: `Journal entry #${res.id} · hash ${shortHash(res.hash)}…`,
      })
      setComment('')
      qc.invalidateQueries({ queryKey: ['declaration', id] })
      qc.invalidateQueries({ queryKey: ['decisions'] })
    } catch (e) {
      toast.error('Could not log the decision', { description: e instanceof Error ? e.message : String(e) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className='flex flex-col gap-3'>
      <div className='grid grid-cols-3 gap-2'>
        <label className='flex flex-col gap-1 text-xs text-muted-foreground'>
          Officer
          <Input value={officer} onChange={(e) => setOfficer(e.target.value)} className='h-8' />
        </label>
        <label className='col-span-2 flex flex-col gap-1 text-xs text-muted-foreground'>
          Comment
          <Input value={comment} onChange={(e) => setComment(e.target.value)} placeholder='e.g. check invoice vs declared value' className='h-8' />
        </label>
      </div>
      <div className='grid grid-cols-3 gap-2'>
        <Button disabled={busy} onClick={() => decide('INSPECT')} className='bg-lane-red text-white hover:bg-lane-red/90'>
          <ShieldAlert /> Inspect
        </Button>
        <Button disabled={busy} onClick={() => decide('DOCUMENT_CHECK')} className='bg-lane-yellow text-black hover:bg-lane-yellow/90'>
          <FileSearch /> Document check
        </Button>
        <Button disabled={busy} onClick={() => decide('RELEASE')} className='bg-lane-green text-black hover:bg-lane-green/90'>
          <ShieldCheck /> Release
        </Button>
      </div>
      {d.decisions.length > 0 && (
        <ul className='flex max-h-36 flex-col gap-1.5 overflow-y-auto'>
          {d.decisions
            .slice()
            .reverse()
            .map((e) => (
              <li key={`${e.id}-${e.hash}`} className='flex items-center justify-between gap-2 rounded-md border bg-muted/30 px-2.5 py-1.5 text-xs'>
                <span className='flex min-w-0 items-center gap-2'>
                  <UserRound className='size-3.5 shrink-0 text-muted-foreground' />
                  <span>{e.officer}</span>
                  <span className='font-semibold'>{e.decision.replace('_', ' ')}</span>
                  {e.comment && <span className='truncate text-muted-foreground'>“{e.comment}”</span>}
                </span>
                <span className='flex shrink-0 items-center gap-1 font-mono text-[10px] text-muted-foreground' title={e.hash}>
                  <Hash className='size-3' />
                  {shortHash(e.hash)}
                </span>
              </li>
            ))}
        </ul>
      )}
      <div className='flex items-center justify-between gap-3 border-t pt-3'>
        <span className='text-[11px] text-muted-foreground'>Demo only: the real outcome is known after inspection.</span>
        <Button variant='outline' size='sm' onClick={() => setReveal((r) => !r)}>
          <Eye /> {reveal ? 'Hide' : 'Reveal'} outcome
        </Button>
      </div>
      {reveal && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className={cn('rounded-lg border p-3 text-sm', d.truth.fraud ? 'border-lane-red/40 bg-lane-red/10' : 'border-lane-green/40 bg-lane-green/10')}
        >
          <span className='font-semibold'>Inspection outcome: </span>
          {d.truth.fraud ? 'fraud found' : 'no fraud'}
          {d.truth.critical ? ' · critical violation (public safety)' : ''}
        </motion.div>
      )}
    </div>
  )
}

function OperatorCard({ h, avg }: { h: OperatorHistory; avg: number }) {
  const rate = h.fraud_rate
  const color = rate == null ? '#64748b' : rate >= 0.4 ? COLORS.red : rate >= 0.2 ? COLORS.yellow : COLORS.green
  return (
    <Card className='gap-1 px-4 py-3'>
      <div className='flex items-center justify-between gap-2'>
        <div className='text-[11px] font-semibold tracking-wider text-muted-foreground uppercase'>{h.role}</div>
        {h.missing ? (
          <Badge variant='outline'>not declared</Badge>
        ) : h.is_new ? (
          <Badge variant='outline'>new</Badge>
        ) : h.thin_history ? (
          <Badge variant='outline' className='border-lane-yellow/40 text-lane-yellow'>
            thin
          </Badge>
        ) : null}
      </div>
      <div className='truncate font-mono text-sm'>{h.id ?? '—'}</div>
      <div className='text-2xl font-semibold tabular-nums' style={{ color }}>
        {rate == null ? '—' : pct(rate)}
      </div>
      <div className='text-[11px] leading-snug text-muted-foreground'>
        {h.missing ? 'treated as average risk' : h.is_new ? 'no past declarations' : `fraud on ${num(h.past_declarations)} past decl. (avg ${pct(avg)})`}
      </div>
    </Card>
  )
}

export function RiskCard({ d }: { d: DeclarationDetailV2 }) {
  const { ai, rule, day } = d
  const agree = (ai.lane === 'RED') === rule.selected
  const prim = ai.models.primary
  return (
    <Card className='gap-4'>
      <CardHeader>
        <CardTitle className='flex flex-wrap items-center gap-2'>
          Risk assessment {ai.uncertain && <UncertainBadge disagreement={ai.disagreement} />}
        </CardTitle>
        <CardDescription>{ai.lane_reason}</CardDescription>
      </CardHeader>
      <CardContent className='flex flex-col gap-4'>
        <div className='grid grid-cols-2 gap-2'>
          <Gauge
            value={ai.p_fraud}
            label={`Duty fraud · ${prim.fraud === 'ebm' ? 'glass box' : 'LightGBM'}`}
            sub={`higher than ${pctile(ai.fraud_percentile)}% of declarations`}
            color={ai.p_fraud >= 0.5 ? COLORS.red : ai.p_fraud >= 0.3 ? COLORS.yellow : COLORS.ai}
          />
          <Gauge
            value={ai.p_critical}
            label={`Public safety · ${prim.critical === 'ebm' ? 'glass box' : 'LightGBM'}`}
            sub={`higher than ${pctile(ai.critical_percentile)}% of declarations`}
            color={ai.alert ? COLORS.red : COLORS.aiLight}
          />
        </div>
        <div className='grid grid-cols-2 gap-2 text-xs'>
          <div className='rounded-lg border bg-muted/30 p-2'>
            <div className='flex items-center gap-1 text-muted-foreground'>
              Glass box vs black box (fraud)
              <InfoTip text='Two independent models score every declaration. When they disagree strongly, RAQIB never releases the declaration green and asks for a human review.' />
            </div>
            <div className='mt-1 flex items-baseline gap-3 tabular-nums'>
              <span>
                EBM <b>{pct(ai.models.ebm.p_fraud)}</b>
              </span>
              <span>
                LightGBM <b>{pct(ai.models.lightgbm.p_fraud)}</b>
              </span>
            </div>
          </div>
          <div className='rounded-lg border bg-muted/30 p-2'>
            <div className='text-muted-foreground'>Today</div>
            <div className='mt-1 tabular-nums'>
              rank <b>{ai.rank_in_day}</b> / {day.n} · capacity <b>{day.capacity}</b>
            </div>
          </div>
        </div>
        <div>
          <div className='text-[11px] font-semibold tracking-wider text-muted-foreground uppercase'>AI vs what the current rule would do</div>
          <div className='mt-2 grid grid-cols-2 gap-2'>
            <div className='rounded-lg border p-3' style={{ borderColor: `${COLORS.ai}55`, background: `${COLORS.ai}10` }}>
              <div className='text-xs text-ai'>RAQIB AI</div>
              <div className='mt-1 text-sm font-semibold' style={{ color: LANE_META[ai.lane].color }}>
                {ai.alert && ai.lane === 'RED' ? 'Inspect · safety alert' : LANE_META[ai.lane].action}
              </div>
            </div>
            <div className='rounded-lg border p-3' style={{ borderColor: `${COLORS.rule}55`, background: `${COLORS.rule}10` }}>
              <div className='text-xs' style={{ color: COLORS.rule }}>
                Current rule · product history
              </div>
              <div className='mt-1 text-sm font-semibold'>{rule.decision === 'INSPECT' ? 'Inspect' : 'Release'}</div>
              <div className='mt-0.5 text-[11px] text-muted-foreground'>
                product: {rule.hs6_past_fraud_rate == null ? 'no history' : `${pct(rule.hs6_past_fraud_rate)} fraud on ${num(rule.hs6_past_declarations)} past`}
              </div>
            </div>
          </div>
          <p className='mt-2 text-[11px] text-muted-foreground'>
            {agree ? 'AI and rule agree on inspection. ' : 'AI and rule disagree here: this is where the measured gain comes from. '}
            {rule.explanation}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

/** Compact inspector for side sheets (worklist, control room). */
export function MiniInspector({ id, rate = 0.05, explore = 0 }: { id: string; rate?: number; explore?: number }) {
  const q = useDeclaration(id, rate, explore)
  if (q.error) return <ErrorState message={String(q.error)} onRetry={() => q.refetch()} />
  if (!q.data) return <Skeleton className='h-96' />
  const d = q.data
  return (
    <div className='flex flex-col gap-4'>
      <div>
        <div className='flex flex-wrap items-center gap-2'>
          <LaneBadge lane={d.ai.lane} alert={d.ai.alert} size='lg' />
          {d.ai.uncertain && <UncertainBadge disagreement={d.ai.disagreement} />}
        </div>
        <p className='mt-2 text-sm'>
          <span className='font-mono'>{d.declaration.hs6}</span> · {d.declaration.hs_desc}
        </p>
        <p className='text-xs text-muted-foreground'>
          {d.declaration.date} · {d.declaration.office_label} · origin {d.declaration.origin} · {compact(d.declaration.item_price)} KRW
        </p>
      </div>
      <div className='grid grid-cols-2 gap-2'>
        <Gauge value={d.ai.p_fraud} label='Duty fraud' color={d.ai.p_fraud >= 0.5 ? COLORS.red : COLORS.ai} />
        <Gauge value={d.ai.p_critical} label='Public safety' color={d.ai.alert ? COLORS.red : COLORS.aiLight} />
      </div>
      <WaterfallChart w={d.waterfall} compact />
      <ReasonList reasons={d.ai.reasons_fraud} compact />
      <DecisionPanel d={d} />
      <Button asChild variant='outline'>
        <Link to='/declaration/$id' params={{ id }}>
          <Gavel /> Open full inspector
        </Link>
      </Button>
    </div>
  )
}

export function FullInspector({ d }: { d: DeclarationDetailV2 }) {
  const { declaration: dc, ai, history, network } = d
  return (
    <div className='flex flex-col gap-4'>
      <div className='grid grid-cols-1 gap-4 xl:grid-cols-12'>
        <div className='flex flex-col gap-4 xl:col-span-5'>
          <RiskCard d={d} />
          <Card className='gap-4'>
            <CardHeader>
              <CardTitle className='flex items-center gap-2'>
                <Gavel className='size-4' /> Officer decision
              </CardTitle>
              <CardDescription>The AI advises; the officer decides. Each decision goes to a hash-chained journal.</CardDescription>
            </CardHeader>
            <CardContent>
              <DecisionPanel d={d} />
            </CardContent>
          </Card>
          <OfficerBrief id={dc.id} />
        </div>
        <div className='flex flex-col gap-4 xl:col-span-7'>
          <Card className='gap-4'>
            <CardHeader>
              <CardTitle>Why this probability — exact waterfall</CardTitle>
              <CardDescription>From the base rate to the final duty-fraud probability, factor by factor</CardDescription>
            </CardHeader>
            <CardContent>
              <WaterfallChart w={d.waterfall} />
            </CardContent>
          </Card>
          <Card className='gap-4'>
            <CardHeader>
              <CardTitle>The 4 strongest reasons — duty fraud</CardTitle>
              <CardDescription>With the real historical numbers behind each factor</CardDescription>
            </CardHeader>
            <CardContent>
              <ReasonList reasons={ai.reasons_fraud} />
            </CardContent>
          </Card>
          <Card className='gap-4'>
            <CardHeader>
              <CardTitle className='flex items-center gap-2'>
                <ShieldAlert className='size-4 text-lane-red' /> Public-safety signals
              </CardTitle>
              <CardDescription>Top 2 factors of the critical-fraud model</CardDescription>
            </CardHeader>
            <CardContent>
              <ReasonList reasons={ai.reasons_critical} compact />
            </CardContent>
          </Card>
        </div>
      </div>
      <div className='grid grid-cols-1 gap-4 xl:grid-cols-12'>
        <div className='flex flex-col gap-3 xl:col-span-5'>
          <div className='grid grid-cols-1 gap-3 sm:grid-cols-3'>
            <OperatorCard h={history.importer} avg={history.average_fraud_rate} />
            <OperatorCard h={history.declarant} avg={history.average_fraud_rate} />
            <OperatorCard h={history.seller} avg={history.average_fraud_rate} />
          </div>
          <Card className='flex-1 gap-3'>
            <CardHeader>
              <CardTitle>Declaration record</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className='grid grid-cols-2 gap-x-6 gap-y-2 text-xs sm:grid-cols-3'>
                {(
                  [
                    ['Declaration ID', dc.id],
                    ['Date', dc.date],
                    ['HS6', dc.hs6],
                    ['Origin / departure', `${dc.origin} / ${dc.departure}`],
                    ['Office', dc.office_label],
                    ['Transport', dc.transport_label],
                    ['Importer', dc.importer],
                    ['Declarant', dc.declarant],
                    ['Seller', dc.seller ?? 'not declared'],
                    ['Tax type / rate', `${dc.tax_type} / ${dc.tax_rate}%`],
                    ['Net mass', `${num(dc.net_mass)} kg`],
                    ['Item price', `${num(dc.item_price)} KRW`],
                    ['Unit value', `${compact(dc.unit_value)} KRW/kg`],
                    ['Process / payment', `${dc.process_type} / ${dc.payment_type}`],
                    ['Origin indicator', dc.origin_indicator],
                  ] as [string, string][]
                ).map(([k, v]) => (
                  <div key={k} className='min-w-0'>
                    <dt className='text-muted-foreground'>{k}</dt>
                    <dd className='truncate font-mono' title={v}>
                      {v}
                    </dd>
                  </div>
                ))}
              </dl>
            </CardContent>
          </Card>
        </div>
        <Card className='gap-3 xl:col-span-7'>
          <CardHeader>
            <CardTitle className='flex items-center gap-2'>
              Operator network <Badge variant='outline'>context only</Badge>
            </CardTitle>
            <CardDescription>
              Past relations of this declarant and seller with other importers. Network features were tested and rejected as model inputs (no
              gain on this data).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <NetworkGraph nodes={network.nodes} links={network.links} avg={history.average_fraud_rate} />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
