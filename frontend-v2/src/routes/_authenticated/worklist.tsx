import { createFileRoute } from '@tanstack/react-router'
import { Worklist } from '@/features/worklist'

export const Route = createFileRoute('/_authenticated/worklist')({
  validateSearch: (s: Record<string, unknown>): { ask?: string; apply?: string } => ({
    ask: typeof s.ask === 'string' && s.ask.trim() ? s.ask : undefined,
    apply: s.apply === '1' || s.apply === 1 ? '1' : undefined,
  }),
  component: Worklist,
})
