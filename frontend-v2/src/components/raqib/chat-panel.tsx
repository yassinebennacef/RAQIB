import { Fragment, useEffect, useRef, useState } from 'react'
import { useLocation } from '@tanstack/react-router'
import { Bot, Loader2, MessageCircle, Minus, Send, Square, Trash2 } from 'lucide-react'
import { clearChat, openChat, sendChat, stopChat, toggleChat, useChat, type ChatMsg } from '@/lib/chat'
import { useMoney } from '@/lib/currency'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { useLlmStatus } from './llm-dot'

const STARTERS = [
  'Explique RAQIB en 3 phrases',
  'Combien de fraudes RAQIB détecte-t-il de plus que la règle ?',
  "Qu'est-ce que l'écart miroir en douane ?",
  'Quels sont les principaux fournisseurs de la Tunisie ?',
]
const DECL_STARTERS = ['Pourquoi cette déclaration est-elle dans ce couloir ?', 'Que dois-je vérifier en priorité ?']

const isArabic = (s: string) => (s.match(/[؀-ۿ]/g)?.length ?? 0) > s.length * 0.3

/** **bold** inside a line */
function Inline({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return (
    <>
      {parts.map((p, i) =>
        p.startsWith('**') && p.endsWith('**') && p.length > 4 ? <b key={i}>{p.slice(2, -2)}</b> : <Fragment key={i}>{p.replace(/^#{1,4}\s+/, '')}</Fragment>
      )}
    </>
  )
}

function Rendered({ text }: { text: string }) {
  const lines = text.split('\n')
  return (
    <div className='flex flex-col gap-1'>
      {lines.map((l, i) => {
        const t = l.trimEnd()
        if (!t.trim()) return <div key={i} className='h-1' />
        const bullet = /^\s*([-•*]|\d+[.)])\s+/.exec(t)
        if (bullet)
          return (
            <div key={i} className='flex gap-1.5 ps-1'>
              <span className='shrink-0 text-muted-foreground'>{/\d/.test(bullet[1]) ? bullet[1] : '•'}</span>
              <span>
                <Inline text={t.slice(bullet[0].length)} />
              </span>
            </div>
          )
        if (/^\s*>/.test(t))
          return (
            <div key={i} className='border-s-2 ps-2 text-muted-foreground'>
              <Inline text={t.replace(/^\s*>\s?/, '')} />
            </div>
          )
        return (
          <div key={i} className={/^#{1,4}\s/.test(t) ? 'font-semibold' : undefined}>
            <Inline text={t} />
          </div>
        )
      })}
    </div>
  )
}

function Bubble({ m, busy, last }: { m: ChatMsg; busy: boolean; last: boolean }) {
  const money = useMoney()
  const mine = m.role === 'user'
  const text = mine ? m.content : money.text(m.content)
  const rtl = isArabic(text)
  return (
    <div className={cn('flex', mine ? 'justify-end' : 'justify-start')}>
      <div
        dir={rtl ? 'rtl' : 'ltr'}
        className={cn(
          'max-w-[88%] rounded-2xl px-3 py-2 text-sm leading-relaxed break-words',
          mine ? 'rounded-br-sm bg-primary text-primary-foreground' : 'rounded-bl-sm border bg-muted/40',
          m.error && 'border-amber-500/50 bg-amber-500/10',
          rtl && 'font-arabic text-base'
        )}
      >
        {mine ? (
          <span className='whitespace-pre-wrap'>{m.content}</span>
        ) : text ? (
          <Rendered text={text} />
        ) : busy && last ? (
          <span className='flex items-center gap-2 text-muted-foreground'>
            <Loader2 className='size-3.5 animate-spin' /> Qwen réfléchit…
          </span>
        ) : null}
      </div>
    </div>
  )
}

/** Floating "Ask Qwen" panel, present on every page (non-modal: the page stays usable). */
export function ChatPanel() {
  const { open, busy, messages } = useChat()
  const { pathname } = useLocation()
  const s = useLlmStatus()
  const on = s.data?.mode === 'ollama'
  const [draft, setDraft] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, open])
  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  const ask = (q: string) => {
    void sendChat(q, pathname)
    setDraft('')
  }
  const starters = pathname.startsWith('/declaration/') ? [...DECL_STARTERS, ...STARTERS.slice(0, 2)] : STARTERS

  if (!open)
    return (
      <button
        type='button'
        data-testid='chat-open'
        onClick={() => openChat()}
        className='fixed end-5 bottom-5 z-[60] flex items-center gap-2 rounded-full bg-primary px-4 py-3 text-sm font-medium text-primary-foreground shadow-lg shadow-black/30 transition-transform hover:scale-105'
        aria-label='Demander à Qwen'
      >
        <MessageCircle className='size-4' /> Demander à Qwen
        {busy && <Loader2 className='size-3.5 animate-spin' />}
      </button>
    )

  return (
    <section
      data-testid='chat-panel'
      aria-label='Discussion avec Qwen'
      className='fixed inset-x-2 bottom-2 z-[60] flex h-[min(640px,calc(100svh-1rem))] flex-col overflow-hidden rounded-xl border bg-background shadow-2xl shadow-black/40 sm:inset-x-auto sm:end-5 sm:bottom-5 sm:w-[420px]'
    >
      <header className='flex items-center gap-2 border-b px-3 py-2'>
        <Bot className='size-4 text-primary' />
        <div className='min-w-0 flex-1'>
          <div className='text-sm font-semibold'>Demander à Qwen</div>
          <div className='flex items-center gap-1.5 truncate text-[10px] text-muted-foreground'>
            <span className={cn('size-1.5 shrink-0 rounded-full', on ? 'bg-lane-green' : 'bg-lane-yellow')} />
            {on ? `${s.data?.model} · local, hors ligne` : 'LLM local indisponible'}
          </div>
        </div>
        <Button variant='ghost' size='icon' className='size-7' title='Effacer la discussion' onClick={clearChat} disabled={!messages.length}>
          <Trash2 className='size-3.5' />
        </Button>
        <Button variant='ghost' size='icon' className='size-7' title='Réduire' onClick={toggleChat} data-testid='chat-close'>
          <Minus className='size-4' />
        </Button>
      </header>

      <div className='flex-1 space-y-3 overflow-y-auto px-3 py-3'>
        {messages.length === 0 && (
          <div className='flex flex-col gap-3 text-sm'>
            <p className='text-muted-foreground'>
              Posez n'importe quelle question (FR, AR, EN) : RAQIB, la douane, les chiffres de cette page ou une question générale. Qwen
              connaît la page ouverte et, sur une déclaration, ses indicateurs de risque.
            </p>
            <div className='flex flex-col gap-1.5'>
              {starters.map((q) => (
                <button
                  key={q}
                  type='button'
                  onClick={() => ask(q)}
                  className='rounded-lg border px-3 py-2 text-start text-xs transition-colors hover:bg-accent'
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <Bubble key={i} m={m} busy={busy} last={i === messages.length - 1} />
        ))}
        <div ref={endRef} />
      </div>

      <form
        className='border-t p-2'
        onSubmit={(e) => {
          e.preventDefault()
          ask(draft)
        }}
      >
        <div className='flex items-end gap-2'>
          <textarea
            ref={inputRef}
            data-testid='chat-input'
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                ask(draft)
              }
            }}
            rows={2}
            maxLength={2000}
            placeholder='Votre question… (Entrée pour envoyer)'
            className='max-h-32 min-h-[2.5rem] flex-1 resize-none rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:border-primary'
          />
          {busy ? (
            <Button type='button' size='icon' variant='outline' onClick={stopChat} title='Arrêter'>
              <Square className='size-3.5' />
            </Button>
          ) : (
            <Button type='submit' size='icon' disabled={!draft.trim()} title='Envoyer' data-testid='chat-send'>
              <Send className='size-4' />
            </Button>
          )}
        </div>
        <p className='mt-1 px-1 text-[10px] leading-snug text-muted-foreground'>
          Réponse générée par Qwen3 en local : elle peut se tromper. Les chiffres officiels de RAQIB sont dans les pages ; l'agent décide.
        </p>
      </form>
    </section>
  )
}
