import type { FindingSeverity, FindingStats } from './types'

const ORDER: FindingSeverity[] = ['Critical', 'High', 'Medium', 'Low', 'Info']

export function normalizeSeverity(value: string): FindingSeverity {
  const normalized = value.trim().toLowerCase()
  if (normalized === 'critical' || normalized === 'blocker') return 'Critical'
  if (normalized === 'high' || normalized === 'error') return 'High'
  if (normalized === 'medium' || normalized === 'moderate' || normalized === 'warning') {
    return 'Medium'
  }
  if (normalized === 'low' || normalized === 'minor') return 'Low'
  return 'Info'
}

export function normalizeStats(stats: Partial<FindingStats>): FindingStats {
  return {
    total_findings: stats.total_findings ?? 0,
    critical_findings: stats.critical_findings ?? 0,
    high_findings: stats.high_findings ?? 0,
    medium_findings: stats.medium_findings ?? 0,
    low_findings: stats.low_findings ?? 0,
    info_findings: stats.info_findings ?? 0,
    by_category: stats.by_category ?? {},
    by_tool: stats.by_tool ?? {},
  }
}

export function topSeverities(stats: FindingStats): string[] {
  return ORDER.filter((severity) => countFor(stats, severity) > 0)
}

function countFor(stats: FindingStats, severity: FindingSeverity): number {
  if (severity === 'Critical') return stats.critical_findings
  if (severity === 'High') return stats.high_findings
  if (severity === 'Medium') return stats.medium_findings
  if (severity === 'Low') return stats.low_findings
  return stats.info_findings
}
