import { createFileRoute } from '@tanstack/react-router'
import { Tunisie } from '@/features/tunisie'

export const Route = createFileRoute('/_authenticated/tunisie')({
  component: Tunisie,
})
