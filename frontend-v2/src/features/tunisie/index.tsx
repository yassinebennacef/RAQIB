import { useQuery } from '@tanstack/react-query'
import { Globe2, Scale, Ship } from 'lucide-react'
import { apiTN, type TnCheckRow, type TnValueRow } from '@/lib/api'
import { useMoney } from '@/lib/currency'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ErrorState, PageShell, Stat } from '@/components/raqib/kit'

const pctFr = (x: number | null | undefined, digits = 0, signed = false) =>
  x == null || !Number.isFinite(x)
    ? '—'
    : `${signed ? (x >= 0 ? '+' : '−') : ''}${Math.abs(x * 100).toLocaleString('fr-FR', { maximumFractionDigits: digits, minimumFractionDigits: digits })} %`

function ValueTable({ rows, kind }: { rows: TnValueRow[]; kind: 'hs2' | 'origin' }) {
  const money = useMoney()
  const max = Math.max(...rows.map((r) => r.usd), 1)
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className='w-8'>#</TableHead>
          <TableHead>{kind === 'hs2' ? 'Chapitre SH' : 'Origine'}</TableHead>
          <TableHead className='text-end'>Importations ({money.label})</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r, i) => (
          <TableRow key={kind === 'hs2' ? r.hs2 : r.code}>
            <TableCell className='text-xs text-muted-foreground tabular-nums'>{i + 1}</TableCell>
            <TableCell className='max-w-[280px]'>
              <div className='truncate text-xs' title={kind === 'hs2' ? r.label : r.name}>
                {kind === 'hs2' ? (
                  <>
                    <span className='font-mono'>{r.hs2}</span> · {r.label}
                  </>
                ) : (
                  r.name
                )}
              </div>
              <div className='mt-1 h-1 rounded-full bg-primary/70' style={{ width: `${(r.usd / max) * 100}%` }} />
            </TableCell>
            <TableCell className='text-end text-xs whitespace-nowrap tabular-nums'>{money.m(r.value, true)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function CheckRow({ label, r }: { label: string; r?: TnCheckRow }) {
  if (!r) return null
  return (
    <TableRow>
      <TableCell className='text-xs font-medium'>{label}</TableCell>
      <TableCell className='text-end text-xs tabular-nums'>{r.n.toLocaleString('fr-FR')}</TableCell>
      <TableCell className='text-end text-xs tabular-nums'>{r.with_ref.toLocaleString('fr-FR')}</TableCell>
      <TableCell className='text-end text-xs font-semibold tabular-nums'>{pctFr(r.share_under, 1)}</TableCell>
    </TableRow>
  )
}

export function Tunisie() {
  const money = useMoney()
  const q = useQuery({ queryKey: ['tunisia'], queryFn: apiTN.tunisia, staleTime: Infinity })
  const t = q.data
  if (q.error && !t) return <ErrorState message={String(q.error)} onRetry={() => q.refetch()} />
  const label = t ? `Données réelles publiques : UN Comtrade (Tunisie, ${t.year})` : 'Données réelles publiques : UN Comtrade (Tunisie)'
  const c = t?.check
  return (
    <PageShell
      title='Contexte tunisien'
      why="Les importations réelles de la Tunisie (statistiques publiques UN Comtrade) : ce qu'elle importe, d'où, et où les chiffres des partenaires divergent. Information seulement : rien ici n'entre dans le modèle."
      actions={<Badge variant='outline'>{label}</Badge>}
    >
      <div className='grid grid-cols-2 gap-3 md:grid-cols-4'>
        <Stat label={`Importations totales ${t?.year ?? ''}`} value={t ? money.m(t.total_imports, true) : <Skeleton className='h-7 w-24' />} sub='toutes marchandises, CIF' />
        <Stat label='1er chapitre importé' value={t ? `SH ${t.top_chapters[0]?.hs2}` : '—'} sub={t?.top_chapters[0]?.label} />
        <Stat label='1re origine' value={t?.top_origins[0]?.name ?? '—'} sub={t ? money.m(t.top_origins[0]?.value, true) : undefined} />
        <Stat label='Références de prix SH6' value={t ? t.n_hs6_ref.toLocaleString('fr-FR') : '—'} sub={t ? `couverture du jeu de test : ${pctFr(c?.coverage)}` : undefined} />
      </div>

      <div className='grid grid-cols-1 gap-4 xl:grid-cols-2'>
        <Card className='gap-2'>
          <CardHeader>
            <CardTitle className='flex items-center gap-2'>
              <Ship className='size-4' /> 15 premiers chapitres importés
            </CardTitle>
            <CardDescription>Importations de la Tunisie par chapitre SH (partenaire : monde), {t?.year}</CardDescription>
          </CardHeader>
          <CardContent>{t ? <ValueTable rows={t.top_chapters} kind='hs2' /> : <Skeleton className='h-96' />}</CardContent>
        </Card>
        <Card className='gap-2'>
          <CardHeader>
            <CardTitle className='flex items-center gap-2'>
              <Globe2 className='size-4' /> 15 premières origines
            </CardTitle>
            <CardDescription>Importations de la Tunisie par pays partenaire, toutes marchandises, {t?.year}</CardDescription>
          </CardHeader>
          <CardContent>{t ? <ValueTable rows={t.top_origins} kind='origin' /> : <Skeleton className='h-96' />}</CardContent>
        </Card>
      </div>

      <Card className='gap-2'>
        <CardHeader>
          <CardTitle className='flex items-center gap-2'>
            <Scale className='size-4' /> Écart miroir — principaux partenaires
          </CardTitle>
          <CardDescription>
            (importations déclarées par la Tunisie − exportations déclarées par le partenaire vers la Tunisie) ÷ exportations du
            partenaire. Écart miroir : indicateur reconnu de sous-facturation, pas une preuve.
          </CardDescription>
        </CardHeader>
        <CardContent className='flex flex-col gap-3'>
          {t ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Partenaire</TableHead>
                  <TableHead className='text-end'>Import. Tunisie ({money.label})</TableHead>
                  <TableHead className='text-end'>Export. partenaire ({money.label})</TableHead>
                  <TableHead className='text-end'>Écart miroir</TableHead>
                  <TableHead>Plus gros chapitres (écart)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {t.mirror.map((m) => (
                  <TableRow key={m.code}>
                    <TableCell className='text-xs font-medium'>{m.name}</TableCell>
                    <TableCell className='text-end text-xs tabular-nums'>{money.m(m.tn_imports, true)}</TableCell>
                    <TableCell className='text-end text-xs tabular-nums'>{m.partner_exports ? money.m(m.partner_exports, true) : 'non déclaré'}</TableCell>
                    <TableCell className='text-end text-xs font-semibold tabular-nums'>{m.reported ? pctFr(m.gap, 1, true) : '—'}</TableCell>
                    <TableCell className='max-w-[360px] truncate text-[11px] text-muted-foreground'>
                      {m.reported
                        ? m.chapters
                            .slice(0, 3)
                            .map((ch) => `${ch.hs2} (${pctFr(ch.gap, 0, true)})`)
                            .join(' · ')
                        : `le partenaire n'a pas publié ses exportations ${t.year}`}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <Skeleton className='h-72' />
          )}
          <p className='text-[11px] text-muted-foreground'>{t?.caveat_mirror}</p>
        </CardContent>
      </Card>

      <Card className='gap-2'>
        <CardHeader>
          <CardTitle>Contrôle mesuré : valeur déclarée vs prix de référence tunisien</CardTitle>
          <CardDescription>
            Part des déclarations du jeu de test dont la valeur/kg est inférieure à {pctFr(t?.threshold)} de la valeur moyenne/kg des
            importations tunisiennes du même SH6. Caveat : {c?.caveat ?? 'données de déclaration synthétiques coréennes × prix de référence réels tunisiens'}.
          </CardDescription>
        </CardHeader>
        <CardContent className='flex flex-col gap-3'>
          {c ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Groupe</TableHead>
                    <TableHead className='text-end'>Déclarations</TableHead>
                    <TableHead className='text-end'>Avec référence</TableHead>
                    <TableHead className='text-end'>Sous 50 % de la réf.</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <CheckRow label='Couloir ROUGE (RAQIB)' r={c.RED} />
                  <CheckRow label='Couloir JAUNE' r={c.YELLOW} />
                  <CheckRow label='Couloir VERT' r={c.GREEN} />
                  <CheckRow label='Fraudes avérées' r={c.fraud} />
                  <CheckRow label='Sans fraude' r={c.no_fraud} />
                </TableBody>
              </Table>
              <p className='rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 text-xs leading-relaxed'>
                <b>Lecture honnête :</b> {pctFr(c.RED?.share_under, 1)} des ROUGES contre {pctFr(c.GREEN?.share_under, 1)} des VERTS : le
                seuil ne sépare pas les couloirs. La valeur déclarée médiane du jeu public vaut {pctFr(c.median_ratio, 1)} du prix de référence
                tunisien : les valeurs synthétiques (CTGAN, jeu coréen) n'ont pas l'échelle des prix réels. Sur de vraies déclarations
                tunisiennes, ce même indicateur deviendrait utilisable ; ici il reste une illustration.
              </p>
            </>
          ) : (
            <Skeleton className='h-40' />
          )}
        </CardContent>
      </Card>

      <p className='text-[11px] text-muted-foreground'>
        {label} · API publique {t?.api} (téléchargée le {t?.fetched}, enregistrée dans data/public_tn ; aucun appel réseau à l'exécution) ·
        montants convertis au taux de référence du {t?.rates.reference_date.split('-').reverse().join('/')} ({t?.rates.reference_source}).
      </p>
    </PageShell>
  )
}
