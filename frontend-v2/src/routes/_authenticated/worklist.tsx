import { createFileRoute } from '@tanstack/react-router'
import { Worklist } from '@/features/worklist'

export const Route = createFileRoute('/_authenticated/worklist')({
  component: Worklist,
})
