import {
  BookOpen,
  Bot,
  BrainCircuit,
  ClipboardList,
  FileCheck2,
  FlaskConical,
  Gauge,
  Globe2,
  Radar,
  ScanSearch,
  ScrollText,
} from 'lucide-react'
import { type SidebarData } from '../types'

export const sidebarData: SidebarData = {
  navGroups: [
    {
      title: 'Opérations',
      items: [
        { title: 'Salle de contrôle', url: '/', icon: Radar },
        { title: 'Liste de travail', url: '/worklist', icon: ClipboardList },
        { title: 'Tester une déclaration', url: '/score', icon: ScanSearch },
      ],
    },
    {
      title: 'Intelligence',
      items: [
        { title: 'Assistant (Qwen3 local)', url: '/assistant', icon: Bot },
        { title: 'Contexte tunisien', url: '/tunisie', icon: Globe2 },
        { title: "Simulateur d'impact", url: '/impact', icon: Gauge },
        { title: 'Explicabilité', url: '/explainability', icon: BrainCircuit },
      ],
    },
    {
      title: 'Gouvernance',
      items: [
        { title: 'Laboratoire du modèle', url: '/lab', icon: FlaskConical },
        { title: 'Fiche du modèle', url: '/model-card', icon: FileCheck2 },
        { title: 'Journal des décisions', url: '/journal', icon: ScrollText },
      ],
    },
    {
      title: 'À propos',
      items: [{ title: 'À propos de RAQIB', url: '/about', icon: BookOpen }],
    },
  ],
}
