import { normalizeSeverity } from '@/lib/utils'

const severityConfig: Record<string, { bg: string; text: string }> = {
  Critical: { bg: 'bg-destructive/10', text: 'text-destructive' },
  High: { bg: 'bg-primary/10', text: 'text-primary' },
  Medium: { bg: 'bg-warning/15', text: 'text-warning' },
  Low: { bg: 'bg-muted', text: 'text-muted-foreground' },
  Info: { bg: 'bg-muted', text: 'text-muted-foreground' },
}

type SeverityBadgeProps = {
  severity: string
  showIcon?: boolean
}

export function SeverityBadge({ severity }: SeverityBadgeProps) {
  const normalized = normalizeSeverity(severity)
  const config = severityConfig[normalized] ?? { bg: 'bg-muted', text: 'text-muted-foreground' }

  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 text-[10px] font-black uppercase tracking-wide rounded-sm ${config.bg} ${config.text}`}>
      {normalized}
    </span>
  )
}
