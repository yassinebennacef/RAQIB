import { useQuery } from '@tanstack/react-query'
import { Cpu, FileCheck2, Printer } from 'lucide-react'
import { apiLLM, apiV2 } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ErrorState, PageShell } from '@/components/raqib/kit'

type Eval = {
  skipped?: boolean
  model?: string | null
  nlq?: { rules?: { exact_match: number; field_accuracy: number }; qwen?: { exact_match: number; field_accuracy: number }; hybrid?: { exact_match: number; field_accuracy: number } }
  brief?: { n: number; guard_pass_rate: number; fallback_rate: number; latency_ms_p50: number; latency_ms_p95: number }
}

const pctx = (x?: number) => (x == null ? '—' : `${Math.round(x * 100)}%`)

function LocalLlmCard() {
  const q = useQuery({ queryKey: ['llm-eval'], queryFn: apiLLM.evaluation })
  const e = q.data as Eval | undefined
  if (!e) return null
  const rows: [string, string][] = [
    ['Model', e.model ?? 'not installed (template mode)'],
    ['Ask RAQIB exact filter: rules-first hybrid', pctx(e.nlq?.hybrid?.exact_match)],
    ['Ask RAQIB: Qwen alone, exact / per field', `${pctx(e.nlq?.qwen?.exact_match)} / ${pctx(e.nlq?.qwen?.field_accuracy)}`],
    ['Brief: numbers verified (guard pass)', pctx(e.brief?.guard_pass_rate)],
    ['Brief: template fallback', pctx(e.brief?.fallback_rate)],
    ['Brief latency p50 / p95', e.brief ? `${(e.brief.latency_ms_p50 / 1000).toFixed(1)} s / ${(e.brief.latency_ms_p95 / 1000).toFixed(1)} s` : '—'],
  ]
  return (
    <Card className='mx-auto w-full max-w-4xl gap-3 px-8 py-6'>
      <h3 className='flex items-center gap-2 text-base font-semibold'>
        <Cpu className='size-4 text-primary' /> Local LLM (optional, offline)
      </h3>
      <p className='text-sm text-foreground/90'>
        The LLM never scores or decides; it only rephrases verified facts and translates questions into filters you confirm.
      </p>
      <div className='grid grid-cols-1 gap-x-8 gap-y-1 text-sm sm:grid-cols-2'>
        {rows.map(([k, v]) => (
          <div key={k} className='flex justify-between gap-4 border-b py-1'>
            <span className='text-muted-foreground'>{k}</span>
            <span className='font-medium tabular-nums'>{v}</span>
          </div>
        ))}
      </div>
      <p className='text-xs text-muted-foreground'>30 test questions (FR / EN / AR) and 70 briefs (50 FR, 10 AR, 10 EN). The rule parser was written alongside these questions, so its score is optimistic; Qwen handles free phrasings the rules do not know.</p>
      {e.skipped && <p className='text-xs text-muted-foreground'>LLM measurements skipped (Ollama not running when evaluated).</p>}
    </Card>
  )
}

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
        <>
        <LocalLlmCard />
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
        </>
      )}
    </PageShell>
  )
}
