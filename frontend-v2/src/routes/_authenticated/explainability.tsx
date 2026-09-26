import { createFileRoute } from '@tanstack/react-router'
import { Explainability } from '@/features/explainability'

export const Route = createFileRoute('/_authenticated/explainability')({
  component: Explainability,
})
