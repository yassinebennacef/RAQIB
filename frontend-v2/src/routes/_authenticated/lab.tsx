import { createFileRoute } from '@tanstack/react-router'
import { ModelLab } from '@/features/model-lab'

export const Route = createFileRoute('/_authenticated/lab')({
  component: ModelLab,
})
