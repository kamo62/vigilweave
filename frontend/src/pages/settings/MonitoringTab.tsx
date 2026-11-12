import { useQuery } from '@tanstack/react-query'
import { Activity, Clock3, Gauge, Wrench } from 'lucide-react'

import { EmptyState } from '@/components/EmptyState'
import { MetricCard } from '@/components/MetricCard'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Separator } from '@/components/ui/separator'
import { fetchSystemMetrics, fetchToolTelemetry } from '@/lib/api'

export function MonitoringTab() {
  const metricsQuery = useQuery({
    queryKey: ['system-metrics'],
    queryFn: fetchSystemMetrics,
    refetchInterval: 10000,
  })
  const telemetryQuery = useQuery({
    queryKey: ['tool-telemetry'],
    queryFn: fetchToolTelemetry,
    refetchInterval: 10000,
  })

  const metrics = metricsQuery.data
  const telemetry = telemetryQuery.data ?? []
  const counters = metrics?.counters ?? {}
  const totalRuns = telemetry.reduce((sum, item) => sum + item.total_runs, 0)
  const failedRuns = telemetry.reduce((sum, item) => sum + item.failed_runs, 0)
  const successRate = totalRuns ? Math.round(((totalRuns - failedRuns) / totalRuns) * 100) : 0

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard
          detail="Seconds since process start"
          icon={<Clock3 size={16} />}
          label="Uptime"
          value={String(Math.round(metrics?.uptime_seconds ?? 0))}
        />
        <MetricCard
          detail="All persisted tool executions"
          icon={<Wrench size={16} />}
          label="Tool Runs"
          value={String(totalRuns)}
        />
        <MetricCard
          detail="Failed executions"
          icon={<Activity size={16} />}
          label="Failures"
          tone={failedRuns > 0 ? 'danger' : 'success'}
          value={String(failedRuns)}
        />
        <MetricCard
          detail="Completed / total"
          icon={<Gauge size={16} />}
          label="Success Rate"
          tone={successRate >= 90 ? 'success' : successRate >= 70 ? 'default' : 'danger'}
          value={`${successRate}%`}
        />
      </div>

      <Card>
        <CardHeader className="px-6 pt-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Runtime
            </p>
            <h2 className="text-lg font-semibold">Process counters</h2>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="space-y-3 p-6">
          {Object.keys(counters).length === 0 ? (
            <EmptyState body="No process counters available." title="No metrics" />
          ) : (
            Object.entries(counters)
              .sort(([a], [b]) => a.localeCompare(b))
              .map(([key, value]) => (
                <div className="rounded-sm border border-border bg-muted/50 p-3" key={key}>
                  <p className="font-mono text-xs text-muted-foreground">{key}</p>
                  <p className="text-lg font-semibold">{value}</p>
                </div>
              ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="px-6 pt-5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-muted-foreground">
              Telemetry
            </p>
            <h2 className="text-lg font-semibold">Per-tool execution profile</h2>
          </div>
        </CardHeader>
        <Separator />
        <CardContent className="space-y-3 p-6">
          {telemetry.length === 0 ? (
            <EmptyState body="Tool telemetry is not populated yet." title="No telemetry" />
          ) : (
            telemetry.map((item) => {
              const failureRate = item.total_runs
                ? Math.round((item.failed_runs / item.total_runs) * 100)
                : 0
              return (
                <Card className="bg-muted/50" key={item.tool}>
                  <CardContent className="gap-2 p-4">
                    <div className="flex items-center justify-between">
                      <p className="font-mono text-sm">{item.tool}</p>
                      <p className="text-xs text-muted-foreground">
                        avg {item.avg_duration_seconds ?? 0}s / {item.avg_findings} findings
                      </p>
                    </div>
                    <Progress
                      aria-label={`${item.tool} failure rate`}
                      color={failureRate < 10 ? 'success' : failureRate < 30 ? 'warning' : 'danger'}
                      maxValue={100}
                      size="sm"
                      value={failureRate}
                    />
                    <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                      <span>total {item.total_runs}</span>
                      <span>completed {item.completed_runs}</span>
                      <span>failed {item.failed_runs}</span>
                      <span>skipped {item.skipped_runs}</span>
                    </div>
                  </CardContent>
                </Card>
              )
            })
          )}
        </CardContent>
      </Card>
    </div>
  )
}
