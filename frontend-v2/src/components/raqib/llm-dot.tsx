import { useQuery } from '@tanstack/react-query'
import { apiLLM } from '@/lib/api'
import { cn } from '@/lib/utils'

export function useLlmStatus() {
  return useQuery({ queryKey: ['llm-status'], queryFn: apiLLM.status, staleTime: 30_000, retry: 0 })
}

export function LlmDot() {
  const s = useLlmStatus()
  const on = s.data?.mode === 'ollama'
  return (
    <span
      className='hidden items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] text-muted-foreground md:flex'
      title={on ? `Local LLM ${s.data?.model} (Ollama, offline)` : 'Local LLM off: template briefs and rule-based questions'}
    >
      <span className={cn('size-2 rounded-full', on ? 'bg-lane-green' : 'bg-muted-foreground/60')} />
      {on ? 'Qwen3 local' : 'Template mode'}
    </span>
  )
}

