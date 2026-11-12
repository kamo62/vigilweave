import { Loader2 } from 'lucide-react'

import { cn } from '@/lib/utils'

type SpinnerProps = {
  className?: string
  label?: string
  size?: number
}

export function Spinner({ className, label, size = 24 }: SpinnerProps) {
  return (
    <div className={cn('flex flex-col items-center gap-2', className)}>
      <Loader2 className="animate-spin text-muted-foreground" size={size} />
      {label ? <p className="text-sm text-muted-foreground">{label}</p> : null}
    </div>
  )
}
