import { Link } from '@tanstack/react-router'
import { Bot, Cpu, FileText, Loader2, RefreshCw, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { PageShell } from '@/components/raqib/kit'
import { ASK_EXAMPLES } from '@/components/raqib/llm'
import { useLlmStatus } from '@/components/raqib/llm-dot'
import { cn } from '@/lib/utils'

const EXAMPLE_DECLARATION = '54794554'

export function Assistant() {
  const s = useLlmStatus()
  const on = s.data?.mode === 'ollama'
  return (
    <PageShell
      title='Assistant local Qwen3'
      why="Deux fonctions seulement, jamais de décision : la note à l'agent (FR / AR / EN) et « Ask RAQIB » (question → filtre de la liste de travail)."
    >
      <Card className='gap-2'>
        <CardHeader>
          <CardTitle className='flex flex-wrap items-center gap-2'>
            <Cpu className='size-4' /> État du modèle local
            <span className={cn('size-2.5 rounded-full', on ? 'bg-lane-green' : 'bg-lane-yellow')} />
            <Badge variant='outline'>{on ? `${s.data?.model} · Ollama` : 'Mode modèle (template)'}</Badge>
            {on && <Badge variant='outline'>{s.data?.warm ? 'chargé en mémoire' : 'pas encore chargé (1er appel plus lent)'}</Badge>}
          </CardTitle>
          <CardDescription>
            {on
              ? `Qwen3 tourne sur cet ordinateur, hors ligne : aucune donnée ne sort.${s.data?.avg_latency_ms ? ` Latence moyenne ${(s.data.avg_latency_ms / 1000).toFixed(1)} s.` : ''}`
              : `LLM local indisponible → mode modèle : les notes et les questions utilisent les versions déterministes. ${s.data?.last_error ?? ''}`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant='outline' size='sm' disabled={s.isFetching} onClick={() => s.refetch()}>
            {s.isFetching ? <Loader2 className='animate-spin' /> : <RefreshCw />} Tester la connexion
          </Button>
        </CardContent>
      </Card>

      <div className='grid gap-4 lg:grid-cols-2'>
        <Card className='gap-3'>
          <CardHeader>
            <CardTitle className='flex items-center gap-2'>
              <Sparkles className='size-4 text-primary' /> Ask RAQIB
            </CardTitle>
            <CardDescription>
              Posez une question en français, anglais ou arabe : RAQIB la traduit en filtre vérifié, l'agent relit les critères puis
              clique « Apply ». Cliquez un exemple :
            </CardDescription>
          </CardHeader>
          <CardContent className='flex flex-col gap-2'>
            {ASK_EXAMPLES.map((ex) => (
              <Link
                key={ex}
                to='/worklist'
                search={{ ask: ex }}
                dir='auto'
                className='rounded-lg border px-3 py-2 text-sm hover:bg-accent'
              >
                {ex}
              </Link>
            ))}
          </CardContent>
        </Card>

        <Card className='gap-3'>
          <CardHeader>
            <CardTitle className='flex items-center gap-2'>
              <FileText className='size-4 text-primary' /> Note à l'agent
            </CardTitle>
            <CardDescription>
              Sur chaque fiche de déclaration, Qwen3 reformule les faits calculés en 3–4 phrases (FR / AR / EN). Chaque chiffre est
              vérifié ; sinon la note déterministe est affichée.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild size='sm'>
              <Link to='/declaration/$id' params={{ id: EXAMPLE_DECLARATION }}>
                <Bot /> Ouvrir un exemple (déclaration {EXAMPLE_DECLARATION})
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
      <p className='text-xs text-muted-foreground'>
        Il n'y a pas de chatbot libre : le LLM ne note pas, ne classe pas et ne décide pas. Il reformule des faits vérifiés et traduit une
        question en filtre, toujours validé par l'agent.
      </p>
    </PageShell>
  )
}
