import { createFileRoute } from '@tanstack/react-router'
import { TryDeclaration } from '@/features/try'

export const Route = createFileRoute('/_authenticated/score')({
  validateSearch: (s: Record<string, unknown>): { hs6?: string } => ({
    hs6: typeof s.hs6 === 'string' || typeof s.hs6 === 'number' ? String(s.hs6) : undefined,
  }),
  component: TryDeclaration,
})
