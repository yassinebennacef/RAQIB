import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { motion } from 'framer-motion'
import { Link2, ShieldCheck, ShieldX } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import { shortHash } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ErrorState, PageShell } from '@/components/raqib/kit'

const DECISION_COLOR: Record<string, string> = { INSPECT: 'text-lane-red', DOCUMENT_CHECK: 'text-lane-yellow', RELEASE: 'text-lane-green' }

export function Journal() {
  const q = useQuery({ queryKey: ['decisions'], queryFn: api.decisions })
  const entries = q.data?.entries ?? []
  const v = q.data?.verify
  const chain = entries.slice(0, 6).reverse()

  return (
    <PageShell
      title='Decision journal'
      why='Every officer decision is appended to a hash-chained journal: editing, deleting or reordering any past line breaks the chain.'
      actions={
        <Button
          onClick={async () => {
            const r = await q.refetch()
            const ok = r.data?.verify.ok
            if (ok) toast.success(`Chain verified: ${r.data?.verify.n_entries} entries, all hashes match`)
            else toast.error(`Chain broken at entry #${r.data?.verify.first_bad_id}`)
          }}
        >
          <ShieldCheck /> Verify chain
        </Button>
      }
    >
      {q.error ? (
        <ErrorState message={String(q.error)} onRetry={() => q.refetch()} />
      ) : !q.data ? (
        <Skeleton className='h-96' />
      ) : (
        <>
          <Card className={cn('flex-row items-center gap-4 px-5 py-4', v?.ok ? 'border-lane-green/40' : 'border-lane-red/40')}>
            {v?.ok ? <ShieldCheck className='size-8 text-lane-green' /> : <ShieldX className='size-8 text-lane-red' />}
            <div>
              <div className='font-semibold'>{v?.ok ? 'Chain intact' : `Chain broken at entry #${v?.first_bad_id}`}</div>
              <div className='text-sm text-muted-foreground'>
                {v?.n_entries ?? 0} decisions · hash = SHA-256(previous hash + canonical record) · stored in artifacts/decisions.jsonl
              </div>
            </div>
          </Card>

          {chain.length > 0 && (
            <Card className='gap-3'>
              <CardHeader>
                <CardTitle>The chain</CardTitle>
                <CardDescription>Each block carries the hash of the previous one</CardDescription>
              </CardHeader>
              <CardContent className='flex items-center gap-2 overflow-x-auto pb-2'>
                {chain.map((e, i) => (
                  <div key={e.id} className='flex items-center gap-2'>
                    {i > 0 && <Link2 className='size-4 shrink-0 text-muted-foreground' />}
                    <motion.div
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.06 }}
                      className='min-w-44 rounded-lg border bg-muted/30 p-2.5 text-[11px]'
                    >
                      <div className='font-semibold'>#{e.id} · <span className={DECISION_COLOR[e.decision]}>{e.decision.replace('_', ' ')}</span></div>
                      <div className='font-mono text-muted-foreground'>prev {shortHash(e.prev_hash, 8)}</div>
                      <div className='font-mono'>hash {shortHash(e.hash, 8)}</div>
                    </motion.div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          <Card className='gap-3 p-4'>
            {entries.length === 0 ? (
              <p className='py-8 text-center text-sm text-muted-foreground'>
                No decision yet. Open a declaration from the <Link to='/worklist' className='text-primary underline'>worklist</Link> and decide.
              </p>
            ) : (
              <div className='overflow-hidden rounded-md border'>
                <Table>
                  <TableHeader>
                    <TableRow>
                      {['#', 'Time (UTC)', 'Declaration', 'Decision', 'AI lane', 'Officer', 'Comment', 'Hash'].map((h) => (
                        <TableHead key={h} className='text-xs'>
                          {h}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {entries.map((e) => (
                      <TableRow key={e.id}>
                        <TableCell className='text-xs tabular-nums'>{e.id}</TableCell>
                        <TableCell className='text-xs'>{e.ts.replace('T', ' ').replace('+00:00', '')}</TableCell>
                        <TableCell>
                          <Link to='/declaration/$id' params={{ id: e.declaration_id }} className='font-mono text-xs text-primary hover:underline'>
                            {e.declaration_id}
                          </Link>
                        </TableCell>
                        <TableCell className={cn('text-xs font-semibold', DECISION_COLOR[e.decision])}>{e.decision.replace('_', ' ')}</TableCell>
                        <TableCell className='text-xs'>{e.ai?.lane ? <Badge variant='outline'>{e.ai.lane}</Badge> : '—'}</TableCell>
                        <TableCell className='text-xs'>{e.officer}</TableCell>
                        <TableCell className='max-w-64 truncate text-xs text-muted-foreground'>{e.comment || '—'}</TableCell>
                        <TableCell className='font-mono text-[10px] text-muted-foreground' title={e.hash}>
                          {shortHash(e.hash, 12)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </Card>
        </>
      )}
    </PageShell>
  )
}
