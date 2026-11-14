import { describe, expect, test } from 'bun:test'

import { evaluateGates } from './gates'

describe('evaluateGates', () => {
  test('fails when critical findings should block', () => {
    const result = evaluateGates(
      {
        total_findings: 2,
        critical_findings: 1,
        high_findings: 0,
        medium_findings: 1,
        low_findings: 0,
        info_findings: 0,
        by_category: {},
        by_tool: {},
      },
      { failOnCritical: true, failOnHigh: false },
    )

    expect(result.passed).toBe(false)
    expect(result.reasons[0]).toContain('Critical')
  })

  test('fails when the server quality gate rejects a completed scan', () => {
    const result = evaluateGates(
      {
        total_findings: 0,
        critical_findings: 0,
        high_findings: 0,
        medium_findings: 0,
        low_findings: 0,
        info_findings: 0,
        by_category: {},
        by_tool: {},
      },
      {
        failOnCritical: false,
        failOnHigh: false,
        qualityGatePassed: false,
        scanStatus: 'completed',
      },
    )

    expect(result.passed).toBe(false)
    expect(result.reasons.join('; ')).toContain('quality gate')
  })

  test('fails a terminal failed scan even when no severity threshold is crossed', () => {
    const result = evaluateGates(
      {
        total_findings: 0,
        critical_findings: 0,
        high_findings: 0,
        medium_findings: 0,
        low_findings: 0,
        info_findings: 0,
        by_category: {},
        by_tool: {},
      },
      {
        failOnCritical: false,
        failOnHigh: false,
        qualityGatePassed: null,
        scanStatus: 'failed',
      },
    )

    expect(result.passed).toBe(false)
    expect(result.reasons.join('; ')).toContain('scan failed')
  })
})
