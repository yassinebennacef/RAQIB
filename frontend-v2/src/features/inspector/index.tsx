import { Link, useParams, useSearch } from '@tanstack/react-router'
import { ArrowLeft, Gavel } from 'lucide-react'
import { useMoney } from '@/lib/currency'
import { num } from '@/lib/format'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState, LaneBadge, PageShell, UncertainBadge } from '@/components/raqib/kit'
import { FullInspector, useDeclaration } from './panel'

export function InspectorPage() {
  const { id } = useParams({ from: '/_authenticated/declaration/$id' })
  const search = useSearch({ from: '/_authenticated/declaration/$id' })
  const q = useDeclaration(id, search.rate ?? 0.05, search.explore ?? 0)
  const d = q.data
  const money = useMoney()
  return (
    <PageShell
      title={`Déclaration ${id}`}
      why={d ? `${d.declaration.hs6} · ${d.declaration.hs_desc}` : 'Loading the declaration…'}
      actions={
        <div className='flex flex-wrap items-center gap-2'>
          {d && <LaneBadge lane={d.ai.lane} alert={d.ai.alert} size='lg' />}
          {d?.ai.uncertain && <UncertainBadge disagreement={d.ai.disagreement} />}
          <Badge variant='outline' className='py-1'>
            <Gavel className='size-3.5' /> Advisory score — the officer decides
          </Badge>
        </div>
      }
    >
      <Link to='/worklist' className='-mt-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground'>
        <ArrowLeft className='size-3.5' /> Worklist
      </Link>
      {d && (
        <p className='-mt-2 text-xs text-muted-foreground'>
          {d.declaration.date} · {d.declaration.office_label} · {d.declaration.transport_label} · origin {d.declaration.origin} · value{' '}
          {d.declaration.value ? money.m(d.declaration.value) : money.krw(d.declaration.item_price)} · {num(d.declaration.net_mass)} kg · taxe {d.declaration.tax_rate}%
        </p>
      )}
      {q.error ? <ErrorState message={String(q.error)} onRetry={() => q.refetch()} /> : d ? <FullInspector d={d} /> : <Skeleton className='h-[600px]' />}
    </PageShell>
  )
}
