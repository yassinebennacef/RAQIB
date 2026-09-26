import { useMemo, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import {
  type ColumnDef,
  type ColumnFiltersState,
  type PaginationState,
  type RowSelectionState,
  type SortingState,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { useSearch } from '@tanstack/react-router'
import { Sparkles, UserCheck, X } from 'lucide-react'
import { toast } from 'sonner'
import { apiLLM, apiV2, type NlqFilter, type WorklistItem } from '@/lib/api'
import { AskRaqib, FilterChips } from '@/components/raqib/llm'
import { COLORS } from '@/lib/colors'
import { compact, num, pct, truncate } from '@/lib/format'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { DataTableBulkActions, DataTableColumnHeader, DataTablePagination, DataTableToolbar } from '@/components/data-table'
import { ErrorState, LaneBadge, PageShell, Stat, UncertainBadge } from '@/components/raqib/kit'
import { MiniInspector } from '@/features/inspector/panel'

const SORTABLE = new Set(['p_fraud', 'p_critical', 'date', 'disagreement', 'item_price'])

export function Worklist() {
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize: 20 })
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([{ id: 'lane', value: ['RED', 'YELLOW'] }])
  const [globalFilter, setGlobalFilter] = useState('')
  const [sorting, setSorting] = useState<SortingState>([{ id: 'p_fraud', desc: true }])
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
  const [openId, setOpenId] = useState<string | null>(null)

  const filter = (id: string) => (columnFilters.find((f) => f.id === id)?.value as string[] | undefined) ?? []
  const unc = filter('uncertain')
  const query = {
    lane: filter('lane').join(','),
    origin: filter('origin').join(','),
    office: filter('office').join(','),
    hs2: filter('hs2').join(','),
    uncertain: unc.length === 1 ? unc[0] === 'true' : undefined,
    q: globalFilter || undefined,
    sort: SORTABLE.has(sorting[0]?.id ?? '') ? sorting[0].id : 'p_fraud',
    order: (sorting[0]?.desc ?? true ? 'desc' : 'asc') as 'asc' | 'desc',
    page: pagination.pageIndex + 1,
    page_size: pagination.pageSize,
  }
  const search = useSearch({ from: '/_authenticated/worklist' })
  const [nlq, setNlq] = useState<{ filter: NlqFilter; label: string } | null>(null)
  const wl = useQuery({
    queryKey: ['worklist', query, nlq, pagination.pageIndex, pagination.pageSize],
    queryFn: () => (nlq ? apiLLM.worklistQuery(nlq.filter, pagination.pageIndex + 1, pagination.pageSize) : apiV2.worklist(query)),
    placeholderData: keepPreviousData,
  })
  const all = useQuery({ queryKey: ['worklist-facets'], queryFn: () => apiV2.worklist({ page_size: 1 }) })
  const F = all.data?.facets

  const columns = useMemo<ColumnDef<WorklistItem>[]>(
    () => [
      {
        id: 'select',
        header: ({ table }) => (
          <Checkbox
            checked={table.getIsAllPageRowsSelected() || (table.getIsSomePageRowsSelected() && 'indeterminate')}
            onCheckedChange={(v) => table.toggleAllPageRowsSelected(!!v)}
            aria-label='Select all'
          />
        ),
        cell: ({ row }) => (
          <Checkbox checked={row.getIsSelected()} onCheckedChange={(v) => row.toggleSelected(!!v)} onClick={(e) => e.stopPropagation()} aria-label='Select row' />
        ),
        enableSorting: false,
      },
      { accessorKey: 'id', header: 'ID', cell: ({ row }) => <span className='font-mono text-xs'>{row.original.id}</span>, enableSorting: false },
      { accessorKey: 'date', header: ({ column }) => <DataTableColumnHeader column={column} title='Date' />, cell: ({ row }) => <span className='text-xs'>{row.original.date}</span> },
      {
        id: 'product',
        header: 'Product',
        cell: ({ row }) => (
          <div className='max-w-[220px] truncate'>
            <span className='font-mono text-xs text-muted-foreground'>{row.original.hs6}</span>{' '}
            <span className='text-xs' title={row.original.hs_desc}>
              {truncate(row.original.hs_desc, 40)}
            </span>
          </div>
        ),
      },
      { accessorKey: 'origin', header: 'Origin', cell: ({ row }) => <span className='text-xs'>{row.original.origin}</span>, enableSorting: false },
      { accessorKey: 'office', header: 'Office', cell: ({ row }) => <span className='text-xs'>{truncate(row.original.office_label, 18)}</span>, enableSorting: false },
      { accessorKey: 'hs2', header: 'Chapter', enableHiding: true, cell: ({ row }) => <span className='text-xs'>{row.original.hs2}</span>, enableSorting: false },
      {
        accessorKey: 'lane',
        header: 'Lane',
        cell: ({ row }) => (
          <div className='flex flex-col items-start gap-1'>
            <LaneBadge lane={row.original.lane} alert={row.original.alert} />
          </div>
        ),
        enableSorting: false,
      },
      {
        accessorKey: 'p_fraud',
        header: ({ column }) => <DataTableColumnHeader column={column} title='Fraud %' />,
        cell: ({ row }) => <span className='font-semibold tabular-nums'>{pct(row.original.p_fraud)}</span>,
      },
      {
        accessorKey: 'p_critical',
        header: ({ column }) => <DataTableColumnHeader column={column} title='Safety %' />,
        cell: ({ row }) => <span className='tabular-nums'>{pct(row.original.p_critical, 1)}</span>,
      },
      {
        accessorKey: 'uncertain',
        header: ({ column }) => <DataTableColumnHeader column={column} title='Models' />,
        cell: ({ row }) => (row.original.uncertain ? <UncertainBadge /> : <span className='text-xs text-muted-foreground'>agree</span>),
        enableSorting: false,
      },
      {
        id: 'top_reason',
        header: 'Top reason',
        cell: ({ row }) => (
          <span className='block max-w-[260px] truncate text-xs text-muted-foreground' title={row.original.top_reason}>
            {row.original.top_reason}
          </span>
        ),
      },
      {
        id: 'rule',
        header: 'Rule would',
        cell: ({ row }) => (
          <span className='text-xs font-medium' style={{ color: row.original.rule_decision === 'INSPECT' ? COLORS.rule : undefined }}>
            {row.original.rule_decision === 'INSPECT' ? 'Inspect' : 'Release'}
          </span>
        ),
      },
      { accessorKey: 'item_price', header: ({ column }) => <DataTableColumnHeader column={column} title='Value' />, cell: ({ row }) => <span className='text-xs tabular-nums'>{compact(row.original.item_price)}</span> },
    ],
    []
  )

  const table = useReactTable({
    data: wl.data?.items ?? [],
    columns,
    getRowId: (r) => r.id,
    state: { pagination, columnFilters, globalFilter, sorting, rowSelection },
    onPaginationChange: setPagination,
    onColumnFiltersChange: (u) => {
      setColumnFilters(u)
      setPagination((p) => ({ ...p, pageIndex: 0 }))
    },
    onGlobalFilterChange: (v) => {
      setGlobalFilter(v)
      setPagination((p) => ({ ...p, pageIndex: 0 }))
    },
    onSortingChange: setSorting,
    onRowSelectionChange: setRowSelection,
    manualPagination: true,
    manualFiltering: true,
    manualSorting: true,
    enableRowSelection: true,
    pageCount: wl.data ? Math.max(1, Math.ceil(wl.data.total / pagination.pageSize)) : 1,
    getCoreRowModel: getCoreRowModel(),
    initialState: { columnVisibility: { hs2: false, item_price: false } },
  })

  const laneOpts = (['RED', 'YELLOW', 'GREEN'] as const).map((l) => ({ label: `${l} (${num(F?.lane[l] ?? 0)})`, value: l }))
  const filters = [
    { columnId: 'lane', title: 'Lane', options: laneOpts },
    { columnId: 'uncertain', title: 'Models', options: [{ label: `Disagree (${num(F?.uncertain.true ?? 0)})`, value: 'true' }, { label: 'Agree', value: 'false' }] },
    { columnId: 'origin', title: 'Origin', options: (F?.origin ?? []).map((o) => ({ label: `${o.value} (${num(o.n)})`, value: o.value })) },
    { columnId: 'office', title: 'Office', options: (F?.office ?? []).map((o) => ({ label: `${truncate(o.label ?? o.value, 28)} (${num(o.n)})`, value: o.value })) },
    { columnId: 'hs2', title: 'HS chapter', options: (F?.hs2 ?? []).map((o) => ({ label: `${o.value} ${truncate(o.label ?? '', 26)} (${num(o.n)})`, value: o.value })) },
  ]
  const selected = Object.keys(rowSelection).length

  return (
    <PageShell
      title='Worklist'
      why="The officer's inbox for the test period: every declaration with its lane, both risks, the models' agreement, the top reason and what the current rule would do."
    >
      <div className='grid grid-cols-2 gap-3 md:grid-cols-4'>
        <Stat label='Inspect (RED)' value={<span className='text-lane-red'>{num(F?.lane.RED ?? 0)}</span>} sub='5% daily capacity' />
        <Stat label='Document check' value={<span className='text-lane-yellow'>{num(F?.lane.YELLOW ?? 0)}</span>} sub='next 10% + models disagree' />
        <Stat label='Release (GREEN)' value={<span className='text-lane-green'>{num(F?.lane.GREEN ?? 0)}</span>} sub='no inspection, no document check' />
        <Stat
          label='Models disagree'
          tip='The glass-box EBM and the LightGBM model disagree strongly: never released green, human review.'
          value={<span className='text-violet-500'>{num(F?.uncertain.true ?? 0)}</span>}
          sub='flagged for human review'
        />
      </div>
      <AskRaqib
        key={`${search.ask ?? 'ask'}-${search.apply ?? ''}`}
        initial={search.ask}
        autoApply={search.apply === '1'}
        onApply={(filter, label) => {
          setNlq({ filter, label })
          setPagination((p) => ({ ...p, pageIndex: 0 }))
        }}
      />
      {nlq && (
        <div className='flex flex-wrap items-center gap-2 rounded-lg border border-primary/40 bg-primary/5 px-3 py-2 text-xs'>
          <Sparkles className='size-3.5 text-primary' />
          <span className='font-medium'>Filtre Ask RAQIB appliqué :</span>
          <FilterChips f={nlq.filter} />
          <Button size='sm' variant='ghost' className='ms-auto h-7' onClick={() => setNlq(null)}>
            <X /> Effacer
          </Button>
        </div>
      )}
      {wl.error && !wl.data ? (
        <ErrorState message={String(wl.error)} onRetry={() => wl.refetch()} />
      ) : (
        <Card className='gap-3 p-4'>
          <DataTableToolbar table={table} searchPlaceholder='Search ID, HS code, product, operator…' filters={filters} />
          <div className='overflow-hidden rounded-md border'>
            <Table>
              <TableHeader>
                {table.getHeaderGroups().map((hg) => (
                  <TableRow key={hg.id}>
                    {hg.headers.map((h) => (
                      <TableHead key={h.id} className='text-xs'>
                        {h.isPlaceholder ? null : flexRender(h.column.columnDef.header, h.getContext())}
                      </TableHead>
                    ))}
                  </TableRow>
                ))}
              </TableHeader>
              <TableBody>
                {!wl.data
                  ? Array.from({ length: 8 }).map((_, i) => (
                      <TableRow key={i}>
                        <TableCell colSpan={columns.length}>
                          <Skeleton className='h-6' />
                        </TableCell>
                      </TableRow>
                    ))
                  : table.getRowModel().rows.map((row) => (
                      <TableRow key={row.id} data-state={row.getIsSelected() && 'selected'} className='cursor-pointer' onClick={() => setOpenId(row.original.id)}>
                        {row.getVisibleCells().map((cell) => (
                          <TableCell key={cell.id} className='py-2'>
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                {wl.data && wl.data.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={columns.length} className='h-24 text-center text-muted-foreground'>
                      No declaration matches these filters.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
          <div className='flex items-center justify-between text-xs text-muted-foreground'>
            <span>{wl.data ? `${num(wl.data.total)} declarations` : ''}</span>
            <Badge variant='outline'>Truth labels are known after inspection (demo)</Badge>
          </div>
          <DataTablePagination table={table} />
          {selected > 0 && (
            <DataTableBulkActions table={table} entityName='declaration'>
              <Button
                size='sm'
                onClick={() => {
                  toast.success(`${selected} declaration${selected > 1 ? 's' : ''} assigned to Agent · Office 30`)
                  setRowSelection({})
                }}
              >
                <UserCheck /> Assign to me
              </Button>
            </DataTableBulkActions>
          )}
        </Card>
      )}
      <Sheet open={openId != null} onOpenChange={(o) => !o && setOpenId(null)}>
        <SheetContent className='w-full overflow-y-auto sm:max-w-xl'>
          <SheetHeader>
            <SheetTitle>Declaration {openId}</SheetTitle>
            <SheetDescription>Mini-inspector · advisory score, the officer decides</SheetDescription>
          </SheetHeader>
          <div className='px-4 pb-6'>{openId && <MiniInspector id={openId} />}</div>
        </SheetContent>
      </Sheet>
    </PageShell>
  )
}
