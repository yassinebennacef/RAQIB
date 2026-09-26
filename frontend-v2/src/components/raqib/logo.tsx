import { COLORS } from '@/lib/colors'

export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox='0 0 32 32' className={className} aria-hidden='true'>
      <rect width='32' height='32' rx='8' fill='#0b1220' />
      <circle cx='16' cy='16' r='11' fill='none' stroke={COLORS.ai} strokeWidth='1.6' opacity='.45' />
      <circle cx='16' cy='16' r='6.5' fill='none' stroke={COLORS.ai} strokeWidth='1.6' opacity='.75' />
      <g className='radar-sweep'>
        <path d='M16 16 L25 9' stroke={COLORS.aiLight} strokeWidth='1.8' strokeLinecap='round' />
        <path d='M16 16 L25 9 A11 11 0 0 1 27 16 Z' fill={COLORS.ai} opacity='.18' />
      </g>
      <circle cx='16' cy='16' r='2.3' fill='#e2e8f0' />
      <circle cx='22.5' cy='20.5' r='1.9' fill={COLORS.red} />
    </svg>
  )
}
