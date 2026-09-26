import { useSyncExternalStore } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiTN, type Money, type Rates } from './api'

/** Display currency: TND by default, remembered in memory for the session (and in sessionStorage if allowed). */
export type Cur = 'tnd' | 'eur' | 'usd'
export const CURRENCIES: Cur[] = ['tnd', 'eur', 'usd']
export const CUR_LABEL: Record<Cur, string> = { tnd: 'TND', eur: 'EUR', usd: 'USD' }

let current: Cur = (() => {
  try {
    const v = sessionStorage.getItem('raqib_cur')
    return v === 'eur' || v === 'usd' || v === 'tnd' ? v : 'tnd'
  } catch {
    return 'tnd'
  }
})()
const listeners = new Set<() => void>()

export function setCurrency(c: Cur) {
  current = c
  try {
    sessionStorage.setItem('raqib_cur', c)
  } catch {
    /* memory only */
  }
  listeners.forEach((l) => l())
}

export function useCurrency(): Cur {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l)
      return () => listeners.delete(l)
    },
    () => current,
    () => current
  )
}

const nf2 = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const nfc = new Intl.NumberFormat('fr-FR', { notation: 'compact', maximumFractionDigits: 1 })

/** French number format: "12 345,67 TND" (compact: "12,3 k TND"). */
export function fmtMoney(x: number | null | undefined, cur: Cur, compact = false): string {
  if (x == null || !Number.isFinite(x)) return '—'
  return `${compact ? nfc.format(x) : nf2.format(x)} ${CUR_LABEL[cur]}`
}

export function krwTo(krw: number, r: Rates, cur: Cur): number {
  const usd = krw / r.krw_per_usd
  return cur === 'usd' ? usd : cur === 'tnd' ? usd * r.tnd_per_usd : (usd * r.tnd_per_usd) / r.tnd_per_eur
}

export function toKrw(x: number, r: Rates, cur: Cur): number {
  const usd = cur === 'usd' ? x : cur === 'tnd' ? x / r.tnd_per_usd : (x * r.tnd_per_eur) / r.tnd_per_usd
  return usd * r.krw_per_usd
}

/** Parse the backend's "1.2M", "34,567", "0.52" number styles (explain.fmt_num). */
function parseNum(s: string): number {
  const m = /^([\d,]*\.?\d+)([kKMB]?)$/.exec(s)
  if (!m) return NaN
  const base = Number(m[1].replace(/,/g, ''))
  return base * ({ k: 1e3, K: 1e3, M: 1e6, B: 1e9 } as Record<string, number>)[m[2] || ''] || base
}

/** Replace every "<n> KRW" / "<n> KRW/kg" in a backend sentence by the amount in the display currency. */
export function localizeText(text: string, r: Rates | undefined, cur: Cur): string {
  if (!text || !r) return text
  return text.replace(/(\d[\d,]*\.?\d*[kKMB]?)\s?KRW(\/kg)?/g, (all, n: string, perKg?: string) => {
    const v = parseNum(n)
    if (!Number.isFinite(v)) return all
    // "2.7M" was already rounded by the backend: stay compact rather than print false decimals
    return `${fmtMoney(krwTo(v, r, cur), cur, /[kKMB]$/.test(n))}${perKg ?? ''}`
  })
}

export function useRates() {
  return useQuery({ queryKey: ['currency'], queryFn: apiTN.currency, staleTime: Infinity })
}

/** Everything a component needs to show dataset amounts (KRW) in the chosen currency. */
export function useMoney() {
  const cur = useCurrency()
  const { data: rates } = useRates()
  return {
    cur,
    rates,
    label: CUR_LABEL[cur],
    /** a {tnd, eur, usd} object from the API */
    m: (x: Money | null | undefined, compact = false) => fmtMoney(x ? x[cur] : null, cur, compact),
    /** a raw dataset amount in KRW */
    krw: (x: number | null | undefined, compact = false) =>
      fmtMoney(x == null || !rates ? null : krwTo(x, rates, cur), cur, compact),
    fromKrw: (x: number) => (rates ? krwTo(x, rates, cur) : NaN),
    toKrw: (x: number) => (rates ? toKrw(x, rates, cur) : NaN),
    text: (s: string) => localizeText(s, rates, cur),
  }
}
