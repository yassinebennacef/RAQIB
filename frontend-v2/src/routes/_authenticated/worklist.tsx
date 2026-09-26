import { createFileRoute } from '@tanstack/react-router'
import { Worklist } from '@/features/worklist'

export const Route = createFileRoute('/_authenticated/worklist')({
  validateSearch: (s: Record<string, unknown>): { ask?: string } => ({
    ask: typeof s.ask === 'string' && s.ask.trim() ? s.ask : undefined,
  }),
  component: Worklist,
})
