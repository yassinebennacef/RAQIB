import { createFileRoute } from '@tanstack/react-router'
import { Journal } from '@/features/journal'

export const Route = createFileRoute('/_authenticated/journal')({
  component: Journal,
})
