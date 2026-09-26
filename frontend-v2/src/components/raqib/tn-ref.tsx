import { Globe2 } from 'lucide-react'
import type { TnRef } from '@/lib/api'
import { useMoney } from '@/lib/currency'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const pctFr = (x: number) => `${x >= 0 ? '+' : '−'}${Math.abs(x * 100).toLocaleString('fr-FR', { maximumFractionDigits: 0 })} %`

/** Declared value/kg vs Tunisia's average import value/kg for the same HS6 (UN Comtrade). Information only. */
export function TunisiaRefCard({ r, compact = false }: { r?: TnRef; compact?: boolean }) {
  const money = useMoney()
  if (!r) return null
  const title = `Référence tunisienne${r.year ? ` (UN Comtrade ${r.year})` : ''}`
  const body = !r.available ? (
    <p className='text-sm text-muted-foreground' data-testid='tn-ref-none'>
      Pas de référence pour ce code SH6 dans les importations tunisiennes publiées.
    </p>
  ) : (
    <div className='flex flex-col gap-2 text-sm' data-testid='tn-ref'>
      <div className='grid grid-cols-2 gap-3'>
        <div>
          <div className='text-[11px] text-muted-foreground'>Valeur déclarée / kg</div>
          <div className='font-semibold tabular-nums'>{money.m(r.declared_per_kg)}/kg</div>
        </div>
        <div>
          <div className='text-[11px] text-muted-foreground'>Moyenne import. Tunisie / kg</div>
          <div className='font-semibold tabular-nums'>{money.m(r.ref_per_kg)}/kg</div>
        </div>
      </div>
      <div className='flex flex-wrap items-center gap-2'>
        <span className='text-xs text-muted-foreground'>Écart :</span>
        <span className='font-semibold tabular-nums'>{pctFr(r.gap ?? 0)}</span>
        {r.under && (
          <Badge variant='outline' className='border-amber-500/50 text-amber-600 dark:text-amber-400'>
            sous-évaluation possible
          </Badge>
        )}
      </div>
      {r.dataset_share_under != null && r.dataset_share_under > 0.5 && (
        <p className='text-[11px] leading-snug text-amber-700 dark:text-amber-300'>
          À relativiser : {(r.dataset_share_under * 100).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} % des déclarations du jeu public sont sous ce seuil (valeur
          médiane = {((r.dataset_median_ratio ?? 0) * 100).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} % de la référence) :
          l'échelle des valeurs synthétiques n'est pas celle des prix réels.
        </p>
      )}
    </div>
  )
  const note = (
    <p className='text-[10px] leading-snug text-muted-foreground'>
      Données réelles publiques : {r.source ?? 'UN Comtrade (Tunisie)'} · information seulement, jamais utilisée par
      le modèle · déclaration synthétique (jeu coréen) comparée à un prix réel tunisien.
    </p>
  )
  if (compact)
    return (
      <div className='rounded-lg border bg-muted/20 p-3'>
        <div className='mb-2 flex items-center gap-2 text-xs font-semibold'>
          <Globe2 className='size-3.5' /> {title}
        </div>
        {body}
        <div className='mt-2'>{note}</div>
      </div>
    )
  return (
    <Card className='gap-3'>
      <CardHeader>
        <CardTitle className='flex items-center gap-2'>
          <Globe2 className='size-4' /> {title}
        </CardTitle>
        <CardDescription>Valeur déclarée par kg face à la valeur moyenne des importations tunisiennes du même SH6</CardDescription>
      </CardHeader>
      <CardContent className='flex flex-col gap-2'>
        {body}
        {note}
      </CardContent>
    </Card>
  )
}
