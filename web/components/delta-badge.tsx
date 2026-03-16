'use client'

interface DeltaBadgeProps {
  value: number | null
}

export function DeltaBadge({ value }: DeltaBadgeProps) {
  if (value === null) return <span className="text-muted-foreground">—</span>
  if (value === 0) return <span className="text-muted-foreground">0</span>
  const isUp = value > 0
  return (
    <span className={isUp ? 'text-emerald-600 font-medium' : 'text-red-500 font-medium'}>
      {isUp ? '+' : ''}{value.toLocaleString()}
    </span>
  )
}
