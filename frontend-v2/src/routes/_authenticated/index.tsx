import { createFileRoute } from '@tanstack/react-router'
import { ControlRoom } from '@/features/control-room'

export const Route = createFileRoute('/_authenticated/')({
  component: ControlRoom,
})
