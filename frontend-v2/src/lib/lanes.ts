import { FileSearch, ShieldAlert, ShieldCheck } from 'lucide-react'
import type { Lane } from './api'
import { COLORS } from './colors'

export const LANE_META: Record<
  Lane,
  { label: string; action: string; color: string; icon: typeof ShieldAlert }
> = {
  RED: { label: 'RED', action: 'Inspect', color: COLORS.red, icon: ShieldAlert },
  YELLOW: { label: 'YELLOW', action: 'Document check', color: COLORS.yellow, icon: FileSearch },
  GREEN: { label: 'GREEN', action: 'Release', color: COLORS.green, icon: ShieldCheck },
}
