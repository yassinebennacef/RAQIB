import { createFileRoute } from '@tanstack/react-router'
import { InspectorPage } from '@/features/inspector'

export const Route = createFileRoute('/_authenticated/declaration/$id')({
  validateSearch: (s: Record<string, unknown>): { rate?: number; explore?: number } => ({
    rate: s.rate != null ? Number(s.rate) : undefined,
    explore: s.explore != null ? Number(s.explore) : undefined,
  }),
  component: InspectorPage,
})
