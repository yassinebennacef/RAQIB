import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { apiLLM } from '@/lib/api'
import { cn } from '@/lib/utils'

export function useLlmStatus() {
  return useQuery({ queryKey: ['llm-status'], queryFn: apiLLM.status, staleTime: 30_000, retry: 0 })
}

export function LlmDot() {
  const s = useLlmStatus()
  const on = s.data?.mode === 'ollama'
  return (
    <Link
      to='/assistant'
      className='hidden items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent md:flex'
      title={
        on
          ? `Assistant local Qwen3: ${s.data?.model} (Ollama, offline)`
          : `LLM local indisponible → mode modèle. ${s.data?.last_error ?? ''}`
      }
    >
      <span className={cn('size-2 rounded-full', on ? 'bg-lane-green' : 'bg-muted-foreground/60')} />
      {on ? 'Qwen3 local' : 'Template mode'}
    </Link>
  )
}

