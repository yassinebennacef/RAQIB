import { createFileRoute } from '@tanstack/react-router'
import { Assistant } from '@/features/assistant'

export const Route = createFileRoute('/_authenticated/assistant')({
  component: Assistant,
})
