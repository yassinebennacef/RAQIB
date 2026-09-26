import { createFileRoute } from '@tanstack/react-router'
import { Impact } from '@/features/impact'

export const Route = createFileRoute('/_authenticated/impact')({
  component: Impact,
})
