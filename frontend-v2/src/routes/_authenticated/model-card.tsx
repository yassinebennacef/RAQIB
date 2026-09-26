import { createFileRoute } from '@tanstack/react-router'
import { ModelCardPage } from '@/features/model-card'

export const Route = createFileRoute('/_authenticated/model-card')({
  component: ModelCardPage,
})
