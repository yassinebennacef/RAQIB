import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useLocation, useNavigate } from '@tanstack/react-router'
import { BookOpen, Bot, Cpu, Loader2, SendHorizontal } from 'lucide-react'
import { toast } from 'sonner'
import { type NlqFilter } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Segmented } from './kit'
import { FilterChips } from './llm'
import { useLlmStatus } from './llm-dot'

type Lang = 'fr' | 'ar' | 'en'

export interface AssistantReply {
  answer: string
  lang: Lang
  dir: 'ltr' | 'rtl'
  source: 'qwen3-4b' | 'faq' | 'rules'
  kind?: 'filter'
  filter?: NlqFilter
  question?: string
  citations: { key: string; title: string; page: string }[]
  guard_passed: boolean
  latency_ms: number
}

type Msg = { role: 'user' | 'assistant'; content: string; reply?: AssistantReply }

const STARTERS: Record<'declaration' | 'general', Record<Lang, string[]>> = {
  declaration: {
    fr: ['Pourquoi cette déclaration est ROUGE ?', 'Que dois-je vérifier en priorité ?', 'Que ferait la règle actuelle ?', "Que veut dire « désaccord des modèles » ?"],
    en: ['Why is this declaration RED?', 'What should I check first?', 'What would the current rule do?', "What does 'models disagree' mean?"],
    ar: ['لماذا هذا التصريح في المسار الأحمر؟', 'ما الذي يجب أن أتحقق منه أولًا؟', 'ماذا كانت ستفعل القاعدة الحالية؟', 'ماذا يعني اختلاف النموذجين؟'],
  },
  general: {
    fr: ['Comment RAQIB choisit les contrôles ?', 'Que signifie précision à 5 % ?', "D'où viennent les données ?", "Que fait l'exploration ?"],
    en: ['How does RAQIB choose the inspections?', 'What does precision at 5% mean?', 'Where does the data come from?', 'What does exploration do?'],
    ar: ['كيف يختار رقيب عمليات التفتيش؟', 'ماذا تعني الدقة عند 5%؟', 'من أين تأتي البيانات؟', 'ما هو الاستكشاف؟'],
  },
}

async function askAssistant(body: { messages: { role: string; content: string }[]; lang: Lang; page: string }) {
  const res = await fetch('/api/assistant', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return (await res.json()) as AssistantReply
}

/* ------------------------------------------------------------------ open/close state shared by button + sidebar */
const Ctx = createContext<{ open: boolean; setOpen: (o: boolean) => void }>({ open: false, setOpen: () => {} })

export function AssistantProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return <Ctx.Provider value={{ open, setOpen }}>{children}</Ctx.Provider>
}

export function useAssistant() {
  return useContext(Ctx)
}

export function AssistantPanel({ className }: { className?: string }) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [lang, setLang] = useState<Lang>('fr')
  const [input, setInput] = useState('')
  const [msgs, setMsgs] = useState<Msg[]>([])
  const endRef = useRef<HTMLDivElement>(null)
  const llm = useLlmStatus()
  const onDecl = pathname.startsWith('/declaration/')
  const starters = STARTERS[onDecl ? 'declaration' : 'general'][lang]

  const send = useMutation({
    mutationFn: (history: Msg[]) =>
      askAssistant({
        messages: history.slice(-6).map((m) => ({ role: m.role, content: m.content })),
        lang,
        page: pathname,
      }),
    onSuccess: (reply) => setMsgs((m) => [...m, { role: 'assistant', content: reply.answer, reply }]),
    onError: (e) => {
      toast.error('Assistant local indisponible', { description: e instanceof Error ? e.message : String(e) })
      setMsgs((m) => [...m, { role: 'assistant', content: 'Assistant indisponible pour le moment. Réessayez.' }])
    },
  })
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [msgs, send.isPending])

  const submit = (text: string) => {
    const t = text.trim()
    if (!t || send.isPending) return
    const next = [...msgs, { role: 'user' as const, content: t }]
    setMsgs(next)
    setInput('')
    send.mutate(next)
  }
  const on = llm.data?.mode === 'ollama'

  return (
    <div className={cn('flex h-full min-h-0 flex-col gap-3', className)}>
      <div className='flex flex-wrap items-center justify-between gap-2'>
        {on ? (
          <Badge variant='outline' className='border-primary/40 text-primary'>
            <Cpu className='size-3' /> Qwen3-4B · local, hors ligne
          </Badge>
        ) : (
          <Badge variant='outline'>
            <BookOpen className='size-3' /> Mode FAQ
          </Badge>
        )}
        <Segmented
          value={lang}
          onChange={setLang}
          options={[
            { value: 'fr', label: 'FR' },
            { value: 'ar', label: 'AR' },
            { value: 'en', label: 'EN' },
          ]}
        />
      </div>
      <p className='text-[11px] text-muted-foreground'>
        L'assistant explique à partir de la base RAQIB et des faits calculés ; il ne note pas, ne classe pas et ne décide pas.
        {onDecl && ' Il utilise les faits de la déclaration ouverte.'}
      </p>
      <div className='min-h-0 flex-1 overflow-y-auto rounded-lg border bg-muted/20 p-3' data-testid='assistant-messages'>
        {msgs.length === 0 && (
          <div className='flex flex-col gap-2'>
            <span className='text-xs text-muted-foreground'>Questions pour commencer :</span>
            {starters.map((s) => (
              <button
                key={s}
                type='button'
                dir='auto'
                onClick={() => submit(s)}
                className='rounded-lg border bg-background px-3 py-2 text-start text-sm hover:bg-accent'
              >
                {s}
              </button>
            ))}
          </div>
        )}
        <div className='flex flex-col gap-3'>
          {msgs.map((m, i) =>
            m.role === 'user' ? (
              <div key={i} dir='auto' className='ms-8 self-end rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground'>
                {m.content}
              </div>
            ) : (
              <div key={i} className='me-6 flex flex-col gap-1.5 rounded-lg border bg-background px-3 py-2' data-testid='assistant-answer'>
                <div dir={m.reply?.dir ?? 'auto'} className={cn('text-sm leading-relaxed whitespace-pre-line', m.reply?.lang === 'ar' && 'font-arabic text-right')}>
                  {m.content}
                </div>
                {m.reply?.kind === 'filter' && m.reply.filter && (
                  <div className='flex flex-col gap-2'>
                    <FilterChips f={m.reply.filter} />
                    <Button
                      size='sm'
                      className='self-start'
                      onClick={() => navigate({ to: '/worklist', search: { ask: m.reply?.question ?? '', apply: '1' } })}
                    >
                      Appliquer
                    </Button>
                  </div>
                )}
                {m.reply && (
                  <div className='flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground'>
                    <span>{m.reply.source === 'qwen3-4b' ? `Qwen3-4B local · ${(m.reply.latency_ms / 1000).toFixed(1)} s` : m.reply.source === 'rules' ? 'Ask RAQIB (règles)' : 'Mode FAQ'}</span>
                    {m.reply.guard_passed && m.reply.source === 'qwen3-4b' && <span className='text-lane-green'>· chiffres vérifiés</span>}
                    {m.reply.citations.map((c) => (
                      <span key={c.key} className='rounded border px-1.5'>
                        {c.title}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )
          )}
          {send.isPending && (
            <div role='status' className='flex items-center gap-2 text-xs text-muted-foreground'>
              <Loader2 className='size-3.5 animate-spin text-primary' /> RAQIB rédige une réponse à partir de la base…
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>
      <form
        className='flex gap-2'
        onSubmit={(e) => {
          e.preventDefault()
          submit(input)
        }}
      >
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          dir='auto'
          placeholder={lang === 'ar' ? 'اكتب سؤالك…' : lang === 'en' ? 'Ask a question…' : 'Posez une question…'}
          aria-label='Question pour l’assistant'
        />
        <Button type='submit' disabled={send.isPending || !input.trim()} aria-label='Envoyer'>
          {send.isPending ? <Loader2 className='animate-spin' /> : <SendHorizontal />}
        </Button>
      </form>
    </div>
  )
}

export function AssistantLauncher() {
  const { open, setOpen } = useAssistant()
  return (
    <>
      <Button
        onClick={() => setOpen(true)}
        className='fixed end-5 bottom-5 z-40 h-11 rounded-full px-4 shadow-lg'
        aria-label='Ouvrir l’assistant RAQIB'
      >
        <Bot /> Assistant
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent className='flex w-full flex-col sm:max-w-lg'>
          <SheetHeader>
            <SheetTitle className='flex items-center gap-2'>
              <Bot className='size-4' /> Assistant RAQIB
            </SheetTitle>
            <SheetDescription>Explique RAQIB et la déclaration ouverte. L'agent décide.</SheetDescription>
          </SheetHeader>
          <AssistantPanel className='px-4 pb-4' />
        </SheetContent>
      </Sheet>
    </>
  )
}
