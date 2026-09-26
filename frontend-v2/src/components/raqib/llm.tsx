import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { BadgeCheck, Cpu, Languages, Loader2, RefreshCw, Sparkles, X } from 'lucide-react'
import { apiLLM, type LlmBrief, type NlqFilter, type NlqResult } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Segmented } from './kit'

/* ------------------------------------------------------------------ Fallback notice (never silent) */
function notifyLlmFallback(kind: LlmBrief['llm_fallback'], detail?: string | null) {
  if (kind === 'unavailable')
    toast.warning('LLM local indisponible → mode modèle', { id: 'llm-unavailable', description: detail ?? undefined })
  else if (kind === 'rejected')
    toast.info('Texte Qwen3 refusé par le garde-fou → note modèle affichée', { id: 'llm-rejected', description: detail ?? undefined })
}

/* ------------------------------------------------------------------ Officer brief */
export function OfficerBrief({ id }: { id: string }) {
  const [lang, setLang] = useState<'fr' | 'ar' | 'en'>('fr')
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['llm-brief', id, lang], queryFn: () => apiLLM.brief(id, lang), retry: 0, staleTime: Infinity })
  const regen = useMutation({
    mutationFn: () => apiLLM.brief(id, lang, true),
    onSuccess: (data) => qc.setQueryData(['llm-brief', id, lang], data),
    onError: (e) => toast.error(`Note non générée : ${e instanceof Error ? e.message : String(e)}`),
  })
  useEffect(() => {
    if (q.data) notifyLlmFallback(q.data.llm_fallback, q.data.llm_error)
  }, [q.data])
  const b = q.data
  const busy = q.isFetching || regen.isPending
  return (
    <Card className='gap-3'>
      <CardHeader>
        <CardTitle className='flex flex-wrap items-center gap-2'>
          <Languages className='size-4' /> Officer brief
          {b &&
            (b.source === 'qwen3-4b' ? (
              <Badge variant='outline' className='border-primary/40 text-primary'>
                <Cpu className='size-3' /> Assistant local Qwen3 · offline
              </Badge>
            ) : (
              <Badge variant='outline' title={b.llm_error ?? undefined}>
                Template{b.llm_fallback === 'unavailable' ? ' · LLM local indisponible' : ''}
              </Badge>
            ))}
          {b?.guard_passed && (
            <Badge variant='outline' className='border-lane-green/40 text-lane-green'>
              <BadgeCheck className='size-3' /> numbers verified
            </Badge>
          )}
        </CardTitle>
        <CardDescription>Rephrases the computed facts only. It never scores or decides; every number is checked against the facts.</CardDescription>
      </CardHeader>
      <CardContent className='flex flex-col gap-3'>
        <div className='flex items-center justify-between gap-2'>
          <Segmented
            value={lang}
            onChange={setLang}
            options={[
              { value: 'fr', label: 'Français' },
              { value: 'ar', label: 'العربية' },
              { value: 'en', label: 'English' },
            ]}
          />
          <Button variant='outline' size='sm' disabled={busy} onClick={() => regen.mutate()}>
            {busy ? <Loader2 className='animate-spin' /> : <RefreshCw />} Regenerate
          </Button>
        </div>
        {!b || busy ? (
          <div className='flex flex-col gap-2'>
            <Skeleton className='h-4 w-full' />
            <Skeleton className='h-4 w-11/12' />
            <Skeleton className='h-4 w-4/5' />
            <Skeleton className='h-4 w-2/3' />
            <span className='text-[11px] text-muted-foreground'>Writing locally on the laptop GPU…</span>
          </div>
        ) : (
          <div
            dir={b.dir}
            lang={b.lang}
            className={cn('text-sm leading-relaxed whitespace-pre-line', b.lang === 'ar' && 'text-right font-arabic text-base')}
          >
            {b.text}
          </div>
        )}
        {b && !busy && (
          <p className='text-[11px] text-muted-foreground'>
            {b.source === 'qwen3-4b'
              ? `${b.model ?? 'Qwen3-4B'} via Ollama · ${b.cached ? 'cached' : `${(b.latency_ms / 1000).toFixed(1)} s`} · no data leaves the laptop`
              : b.llm_fallback === 'unavailable'
                ? `Deterministic template: LLM local indisponible (${b.llm_error ?? 'Ollama not reachable'}).`
                : b.llm_fallback === 'rejected'
                  ? `Deterministic template: the Qwen3 text was rejected by the guard (${b.llm_error ?? ''}).`
                  : 'Deterministic template built from the facts (local LLM switched off).'}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

/* ------------------------------------------------------------------ Ask RAQIB */
export const ASK_EXAMPLES = [
  "déclarations rouges d'origine CN au chapitre 85 au-dessus de 80%",
  'show uncertain cases from office 20',
  'الحالات ذات التنبيه الأمني',
]

type ChipKey = keyof NlqFilter

function chipsOf(f: NlqFilter): { key: ChipKey; value?: string; label: string }[] {
  const out: { key: ChipKey; value?: string; label: string }[] = []
  for (const l of f.lane ?? []) out.push({ key: 'lane', value: l, label: `Lane ${l}` })
  if (f.safety_only) out.push({ key: 'safety_only', label: 'Safety alerts' })
  if (f.uncertain_only) out.push({ key: 'uncertain_only', label: 'Models disagree' })
  if (f.min_fraud != null) out.push({ key: 'min_fraud', label: `Fraud ≥ ${Math.round(f.min_fraud * 100)}%` })
  for (const o of f.origin ?? []) out.push({ key: 'origin', value: o, label: `Origin ${o}` })
  for (const h of f.hs_prefix ?? []) out.push({ key: 'hs_prefix', value: h, label: `HS ${h}` })
  for (const o of f.office ?? []) out.push({ key: 'office', value: o, label: `Office ${o}` })
  if (f.importer) out.push({ key: 'importer', label: `Importer ${f.importer}` })
  if (f.date_from || f.date_to) out.push({ key: 'date_from', label: `${f.date_from ?? '…'} → ${f.date_to ?? '…'}` })
  out.push({ key: 'sort', label: { fraud_desc: 'by fraud risk', critical_desc: 'by safety risk', date_desc: 'most recent' }[f.sort] })
  out.push({ key: 'limit', label: `top ${f.limit}` })
  return out
}

function removeChip(f: NlqFilter, c: { key: ChipKey; value?: string }): NlqFilter {
  const n: NlqFilter = { ...f }
  if (c.key === 'lane' || c.key === 'origin' || c.key === 'hs_prefix' || c.key === 'office') {
    const arr = ((n[c.key] as string[] | null) ?? []).filter((x) => x !== c.value)
    ;(n as unknown as Record<string, unknown>)[c.key] = arr.length ? arr : null
  } else if (c.key === 'safety_only' || c.key === 'uncertain_only') n[c.key] = false
  else if (c.key === 'min_fraud' || c.key === 'importer') n[c.key] = null
  else if (c.key === 'date_from') {
    n.date_from = null
    n.date_to = null
  } else if (c.key === 'sort') n.sort = 'fraud_desc'
  else if (c.key === 'limit') n.limit = 50
  return n
}

export function FilterChips({ f, onRemove }: { f: NlqFilter; onRemove?: (c: { key: ChipKey; value?: string }) => void }) {
  return (
    <div className='flex flex-wrap gap-1.5'>
      {chipsOf(f).map((c, i) => (
        <span key={`${c.key}-${c.value ?? i}`} className='inline-flex items-center gap-1 rounded-full border bg-muted/40 px-2.5 py-0.5 text-xs'>
          {c.label}
          {onRemove && c.key !== 'sort' && c.key !== 'limit' && (
            <button type='button' aria-label={`Remove ${c.label}`} onClick={() => onRemove(c)} className='text-muted-foreground hover:text-foreground'>
              <X className='size-3' />
            </button>
          )}
        </span>
      ))}
    </div>
  )
}

export function AskRaqib({ initial, onApply }: { initial?: string; onApply: (f: NlqFilter, label: string) => void }) {
  const [q, setQ] = useState(initial ?? '')
  const [res, setRes] = useState<NlqResult | null>(null)
  const [pending, setPending] = useState<NlqFilter | null>(null)
  const ask = useMutation({
    mutationFn: (text: string) => apiLLM.nlq(text),
    onSuccess: (r) => {
      setRes(r)
      setPending(r.filter)
      notifyLlmFallback(r.llm_fallback, r.warnings[0])
    },
    onError: (e) => toast.error(`Question non comprise : ${e instanceof Error ? e.message : String(e)}`),
  })
  useEffect(() => {
    if (initial && initial.trim()) ask.mutate(initial.trim())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial])
  return (
    <Card className='gap-3 border-primary/30 p-4'>
      <form
        className='flex flex-wrap items-center gap-2'
        onSubmit={(e) => {
          e.preventDefault()
          if (q.trim()) ask.mutate(q.trim())
        }}
      >
        <Sparkles className='size-4 text-primary' />
        <span className='text-sm font-semibold'>Ask RAQIB</span>
        <Badge variant='outline' className='text-[10px]'>Assistant local Qwen3</Badge>
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={ASK_EXAMPLES[0]}
          className='h-9 min-w-[280px] flex-1'
          dir='auto'
          aria-label='Ask RAQIB in French, English or Arabic'
        />
        <Button type='submit' size='sm' disabled={ask.isPending || !q.trim()}>
          {ask.isPending ? <Loader2 className='animate-spin' /> : <Sparkles />} Understand
        </Button>
      </form>
      {!res && (
        <div className='flex flex-wrap gap-2 text-xs text-muted-foreground'>
          Try:
          {ASK_EXAMPLES.map((ex) => (
            <button
              key={ex}
              type='button'
              dir='auto'
              className='rounded-full border px-2 py-0.5 hover:bg-accent hover:text-foreground'
              onClick={() => {
                setQ(ex)
                ask.mutate(ex)
              }}
            >
              {ex}
            </button>
          ))}
        </div>
      )}
      {res && pending && (
        <div className='flex flex-col gap-2'>
          <div className='flex flex-wrap items-center gap-2 text-xs text-muted-foreground'>
            Understood as
            <Badge variant='outline'>{res.source === 'qwen3-4b' ? 'Qwen3-4B · local' : 'rule-based parser (exact match, Qwen not needed)'}</Badge>
            — review, remove what you do not want, then apply (never applied automatically).
          </div>
          <FilterChips f={pending} onRemove={(c) => setPending(removeChip(pending, c))} />
          {res.warnings.length > 0 && <div className='text-[11px] text-lane-yellow'>{res.warnings.join(' · ')}</div>}
          <div className='flex gap-2'>
            <Button size='sm' onClick={() => onApply(pending, res.explanation)}>
              Apply filter
            </Button>
            <Button
              size='sm'
              variant='ghost'
              onClick={() => {
                setRes(null)
                setPending(null)
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}
