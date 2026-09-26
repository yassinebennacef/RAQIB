import { useSyncExternalStore } from 'react'

/** Chat with the local Qwen3: one conversation for the whole session, shared by every page. */
export type ChatMsg = { role: 'user' | 'assistant'; content: string; error?: boolean; page?: string }

type State = { open: boolean; busy: boolean; messages: ChatMsg[] }

const KEY = 'raqib_chat'

/** The conversation survives a page reload within the browser tab (sessionStorage), when storage is allowed. */
function load(): State {
  try {
    const v = JSON.parse(sessionStorage.getItem(KEY) || 'null')
    if (v && Array.isArray(v.messages)) return { open: Boolean(v.open), busy: false, messages: v.messages.slice(-40) }
  } catch {
    /* memory only */
  }
  return { open: false, busy: false, messages: [] }
}

let state: State = load()
const listeners = new Set<() => void>()
let controller: AbortController | null = null

function set(patch: Partial<State>) {
  state = { ...state, ...patch }
  listeners.forEach((l) => l())
  if (!state.busy) {
    try {
      sessionStorage.setItem(KEY, JSON.stringify({ open: state.open, messages: state.messages.slice(-40) }))
    } catch {
      /* memory only */
    }
  }
}

export function useChat(): State {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
    () => state,
    () => state
  )
}

export const openChat = (open = true) => set({ open })
export const toggleChat = () => set({ open: !state.open })

export function clearChat() {
  controller?.abort()
  set({ messages: [], busy: false })
}

export function stopChat() {
  controller?.abort()
}

function setLast(update: (m: ChatMsg) => ChatMsg) {
  const msgs = state.messages.slice()
  msgs[msgs.length - 1] = update(msgs[msgs.length - 1])
  set({ messages: msgs })
}

/** Send a question; the answer is streamed into the last message. */
export async function sendChat(question: string, page: string) {
  const q = question.trim()
  if (!q || state.busy) return
  const history = [...state.messages.filter((m) => !m.error), { role: 'user' as const, content: q }]
  set({
    busy: true,
    open: true,
    messages: [...state.messages, { role: 'user', content: q, page }, { role: 'assistant', content: '' }],
  })
  controller = new AbortController()
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: history.map(({ role, content }) => ({ role, content })), page }),
      signal: controller.signal,
    })
    if (!res.ok || !res.body) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        if (body?.detail) detail = String(body.detail)
      } catch {
        /* not JSON */
      }
      setLast((m) => ({
        ...m,
        error: true,
        content:
          res.status === 503
            ? `${detail}\n\nDémarrez Ollama sur cet ordinateur (commande : ollama serve), puis réessayez. Page « Assistant (Qwen3 local) » pour tester la connexion.`
            : `Erreur : ${detail}`,
      }))
      return
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      const piece = decoder.decode(value, { stream: true })
      if (piece) setLast((m) => ({ ...m, content: m.content + piece }))
    }
    const tail = decoder.decode()
    if (tail) setLast((m) => ({ ...m, content: m.content + tail }))
    if (!state.messages[state.messages.length - 1]?.content.trim())
      setLast((m) => ({ ...m, error: true, content: 'Le modèle a renvoyé une réponse vide. Reformulez la question.' }))
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') {
      setLast((m) => ({ ...m, content: m.content ? `${m.content}\n\n[arrêté]` : '[arrêté]' }))
    } else {
      setLast((m) => ({ ...m, error: true, content: `Serveur RAQIB injoignable (${String(err)}). Le backend tourne-t-il ?` }))
    }
  } finally {
    controller = null
    set({ busy: false })
  }
}
