import { Card } from '@/components/ui/card'
import { AssistantPanel } from '@/components/raqib/assistant'
import { PageShell } from '@/components/raqib/kit'

export function AssistantPage() {
  return (
    <PageShell
      title='Assistant RAQIB'
      why="Posez vos questions sur RAQIB (voies, modèles, résultats, données) : réponses ancrées dans la base RAQIB, en français, arabe ou anglais. L'assistant explique ; il ne décide jamais."
    >
      <Card className='h-[70vh] p-4'>
        <AssistantPanel />
      </Card>
    </PageShell>
  )
}
