import { useQuery } from '@tanstack/react-query'
import { FileCheck2, Printer } from 'lucide-react'
import { apiV2 } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ErrorState, PageShell } from '@/components/raqib/kit'

export function ModelCardPage() {
  const q = useQuery({ queryKey: ['model-card'], queryFn: apiV2.modelCard })
  const c = q.data
  return (
    <PageShell
      title='Model card'
      why='Governance: what RAQIB is for, what it must never be used for, how well it works and how it is overseen.'
      actions={
        <Button variant='outline' size='sm' onClick={() => window.print()}>
          <Printer /> Print
        </Button>
      }
    >
      {q.error ? (
        <ErrorState message={String(q.error)} onRetry={() => q.refetch()} />
      ) : !c ? (
        <Skeleton className='h-[600px]' />
      ) : (
        <Card className='mx-auto w-full max-w-4xl gap-0 py-8'>
          <CardContent className='flex flex-col gap-6 px-8'>
            <div className='flex items-center gap-3 border-b pb-4'>
              <FileCheck2 className='size-8 text-primary' />
              <div>
                <h2 className='text-xl font-bold'>{c.title}</h2>
                <p className='text-xs text-muted-foreground'>
                  Version {c.version} · generated {c.generated_at} from the measured artifacts
                </p>
              </div>
            </div>
            {c.sections.map((s) => (
              <section key={s.key} className='flex flex-col gap-2'>
                <h3 className='text-base font-semibold'>{s.title}</h3>
                {s.text && <p className='text-sm leading-relaxed text-foreground/90'>{s.text}</p>}
                {s.bullets && s.bullets.length > 0 && (
                  <ul className='list-disc space-y-1 ps-5 text-sm leading-relaxed text-foreground/90'>
                    {s.bullets.map((b) => (
                      <li key={b}>{b}</li>
                    ))}
                  </ul>
                )}
                {s.table && (
                  <div className='overflow-x-auto rounded-md border'>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          {s.table.columns.map((col) => (
                            <TableHead key={col} className='text-xs'>
                              {col}
                            </TableHead>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {s.table.rows.map((row, i) => (
                          <TableRow key={i}>
                            {row.map((cell, j) => (
                              <TableCell key={j} className='text-xs tabular-nums'>
                                {String(cell)}
                              </TableCell>
                            ))}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </section>
            ))}
          </CardContent>
        </Card>
      )}
    </PageShell>
  )
}
