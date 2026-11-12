import type { ReactNode } from 'react'

import { Card, CardContent } from '@/components/ui/card'

type MetricCardProps = {
  label: string
  value: string
  tone?: 'default' | 'danger' | 'success'
  detail?: string
  icon?: ReactNode
}

const toneStyles: Record<string, string> = {
  default: '',
  danger: 'border-danger/20 bg-danger/[0.06]',
  success: 'border-success/20 bg-success/[0.06]',
}

export function MetricCard({ label, value, tone = 'default', detail, icon }: MetricCardProps) {
  return (
    <Card className={toneStyles[tone]}>
      <CardContent className="gap-1 p-4">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
            {label}
          </span>
          {icon ? <span className="text-muted-foreground">{icon}</span> : null}
        </div>
        <p className="text-2xl font-bold tracking-tight text-foreground">{value}</p>
        {detail ? <p className="text-xs text-muted-foreground">{detail}</p> : null}
      </CardContent>
    </Card>
  )
}
