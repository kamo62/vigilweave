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
})
