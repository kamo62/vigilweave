import type { FindingStats, GateEvaluation } from './types'

export function evaluateGates(
  stats: FindingStats,
  options: {
    failOnCritical: boolean
    failOnHigh: boolean
    qualityGatePassed?: boolean | null
    scanStatus?: string
  },
): GateEvaluation {
  const reasons: string[] = []
  if (options.scanStatus === 'failed') {
    reasons.push('VigilWeave scan failed.')
  } else if (options.scanStatus && options.scanStatus !== 'completed') {
    reasons.push(`VigilWeave scan ended with unexpected status: ${options.scanStatus}.`)
  }
  if (options.qualityGatePassed === false) {
    reasons.push('VigilWeave quality gate failed.')
  }
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
