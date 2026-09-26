import React, { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { ArrowRight, FileSearch, Laptop, Moon, Package, Sun } from 'lucide-react'
import { api, apiV2 } from '@/lib/api'
import { pct, truncate } from '@/lib/format'
import { useSearch } from '@/context/search-provider'
import { useTheme } from '@/context/theme-provider'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/components/ui/command'
import { sidebarData } from './layout/data/sidebar-data'
import { ScrollArea } from './ui/scroll-area'

function useDebounced<T>(value: T, ms = 200): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const id = window.setTimeout(() => setV(value), ms)
    return () => window.clearTimeout(id)
  }, [value, ms])
  return v
}

export function CommandMenu() {
  const navigate = useNavigate()
  const { setTheme } = useTheme()
  const { open, setOpen } = useSearch()
  const [query, setQuery] = useState('')
  const q = useDebounced(query.trim())

  const decl = useQuery({
    queryKey: ['cmd-decl', q],
    queryFn: () => apiV2.worklist({ q, page_size: 6, sort: 'p_fraud' }),
    enabled: open && q.length >= 3,
  })
  const hs = useQuery({
    queryKey: ['cmd-hs', q],
    queryFn: () => api.hsSearch(q),
    enabled: open && q.length >= 2 && !/^\d{5,}$/.test(q),
  })

  const runCommand = React.useCallback(
    (command: () => unknown) => {
      setOpen(false)
      setQuery('')
      command()
    },
    [setOpen]
  )

  return (
    <CommandDialog modal open={open} onOpenChange={setOpen}>
      <CommandInput
        placeholder='Declaration ID, product (e.g. coffee, 8517) or page…'
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        <ScrollArea type='hover' className='h-80 pe-1'>
          <CommandEmpty>No results found.</CommandEmpty>
          {(decl.data?.items.length ?? 0) > 0 && (
            <CommandGroup heading='Declarations (test period)'>
              {decl.data!.items.map((d) => (
                <CommandItem
                  key={d.id}
                  value={`decl ${d.id} ${d.hs6} ${d.hs_desc} ${query}`}
                  onSelect={() => runCommand(() => navigate({ to: '/declaration/$id', params: { id: d.id } }))}
                >
                  <FileSearch className='text-muted-foreground' />
                  <span className='font-mono'>{d.id}</span>
                  <span className='truncate text-muted-foreground'>{truncate(d.hs_desc, 50)}</span>
                  <span className='ms-auto text-xs tabular-nums'>{pct(d.p_fraud)}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
          {(hs.data?.length ?? 0) > 0 && (
            <CommandGroup heading='Products (HS6) — score a declaration'>
              {hs.data!.slice(0, 8).map((h) => (
                <CommandItem
                  key={h.hs6}
                  value={`hs ${h.hs6} ${h.description} ${query}`}
                  onSelect={() => runCommand(() => navigate({ to: '/score', search: { hs6: h.hs6 } }))}
                >
                  <Package className='text-muted-foreground' />
                  <span className='font-mono'>{h.hs6}</span>
                  <span className='truncate'>{truncate(h.description, 60)}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
          {sidebarData.navGroups.map((group) => (
            <CommandGroup key={group.title} heading={group.title}>
              {group.items.map((navItem, i) =>
                navItem.url ? (
                  <CommandItem
                    key={`${navItem.url}-${i}`}
                    value={navItem.title}
                    onSelect={() => runCommand(() => navigate({ to: navItem.url }))}
                  >
                    <div className='flex size-4 items-center justify-center'>
                      <ArrowRight className='size-2 text-muted-foreground/80' />
                    </div>
                    {navItem.title}
                  </CommandItem>
                ) : null
              )}
            </CommandGroup>
          ))}
          <CommandSeparator />
          <CommandGroup heading='Theme'>
            <CommandItem onSelect={() => runCommand(() => setTheme('light'))}>
              <Sun /> <span>Light</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => setTheme('dark'))}>
              <Moon className='scale-90' />
              <span>Dark</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => setTheme('system'))}>
              <Laptop />
              <span>System</span>
            </CommandItem>
          </CommandGroup>
        </ScrollArea>
      </CommandList>
    </CommandDialog>
  )
}
