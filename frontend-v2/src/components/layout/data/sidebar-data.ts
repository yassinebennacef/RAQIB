import {
  Bot,
  BookOpen,
  BrainCircuit,
  ClipboardList,
  FileCheck2,
  FlaskConical,
  Gauge,
  Radar,
  ScanSearch,
  ScrollText,
} from 'lucide-react'
import { type SidebarData } from '../types'

export const sidebarData: SidebarData = {
  navGroups: [
    {
      title: 'Operations',
      items: [
        { title: 'Control room', url: '/', icon: Radar },
        { title: 'Worklist', url: '/worklist', icon: ClipboardList },
        { title: 'Try a declaration', url: '/score', icon: ScanSearch },
      ],
    },
    {
      title: 'Intelligence',
      items: [
        { title: 'Impact simulator', url: '/impact', icon: Gauge },
        { title: 'Explainability', url: '/explainability', icon: BrainCircuit },
        { title: 'Assistant RAQIB', url: '/assistant', icon: Bot },
      ],
    },
    {
      title: 'Governance',
      items: [
        { title: 'Model lab', url: '/lab', icon: FlaskConical },
        { title: 'Model card', url: '/model-card', icon: FileCheck2 },
        { title: 'Decision journal', url: '/journal', icon: ScrollText },
      ],
    },
    {
      title: 'About',
      items: [{ title: 'About RAQIB', url: '/about', icon: BookOpen }],
    },
  ],
}
