import { describe, expect, test } from 'bun:test'

import { evaluateGates } from './gates'

const emptyStats = {
  total_findings: 0,
  critical_findings: 0,
  high_findings: 0,
  medium_findings: 0,
  low_findings: 0,
  info_findings: 0,
  by_category: {},
  by_tool: {},
}

describe('evaluateGates', () => {
  test('honours a failed server quality gate', () => {
    const result = evaluateGates(emptyStats, {
      failOnCritical: false,
      failOnHigh: false,
      qualityGatePassed: false,
      scanStatus: 'completed',
    })

    expect(result.passed).toBe(false)
    expect(result.reasons.join('; ')).toContain('quality gate')
  })

  test('fails an incomplete scan even when severity thresholds pass', () => {
    const result = evaluateGates(emptyStats, {
      failOnCritical: false,
      failOnHigh: false,
      qualityGatePassed: null,
      scanStatus: 'failed',
    })

    expect(result.passed).toBe(false)
    expect(result.reasons.join('; ')).toContain('scan failed')
  })

  test('keeps configured severity thresholds active when the server gate passes', () => {
    const result = evaluateGates(
      { ...emptyStats, high_findings: 1 },
      {
        failOnCritical: false,
        failOnHigh: true,
        qualityGatePassed: true,
        scanStatus: 'completed',
      },
    )

    expect(result.passed).toBe(false)
    expect(result.reasons.join('; ')).toContain('High findings')
  })
})
