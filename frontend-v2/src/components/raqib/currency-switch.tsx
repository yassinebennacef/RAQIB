import { CURRENCIES, CUR_LABEL, setCurrency, useCurrency } from '@/lib/currency'
import { cn } from '@/lib/utils'

/** TND | EUR | USD, default TND; the choice is kept for the session. */
export function CurrencySwitch() {
  const cur = useCurrency()
  return (
    <div role='radiogroup' aria-label='Devise' className='flex items-center rounded-md border p-0.5 text-xs'>
      {CURRENCIES.map((c) => (
        <button
          key={c}
          type='button'
          role='radio'
          aria-checked={cur === c}
          data-testid={`cur-${c}`}
          onClick={() => setCurrency(c)}
          className={cn(
            'rounded px-2 py-1 font-medium tabular-nums transition-colors',
            cur === c ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
          )}
        >
          {CUR_LABEL[c]}
        </button>
      ))}
    </div>
  )
}
