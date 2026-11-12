import type { FindingStats, GateEvaluation } from './types'

export function evaluateGates(
  stats: FindingStats,
  options: { failOnCritical: boolean; failOnHigh: boolean },
): GateEvaluation {
  const reasons: string[] = []
  if (options.failOnCritical && stats.critical_findings > 0) {
    reasons.push(`Critical findings detected: ${stats.critical_findings}`)
  }
  if (options.failOnHigh && stats.high_findings > 0) {
    reasons.push(`High findings detected: ${stats.high_findings}`)
  }
  return {
    passed: reasons.length === 0,
    reasons,
  }
}
