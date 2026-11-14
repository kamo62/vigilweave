import { describe, expect, test } from 'bun:test'

import { pollingDecision } from './scanStatus'

describe('pollingDecision', () => {
  test('keeps polling known nonterminal states', () => {
    expect(pollingDecision('queued')).toBe('pending')
    expect(pollingDecision('running')).toBe('pending')
  })

  test('returns terminal states and rejects unexpected states', () => {
    expect(pollingDecision('completed')).toBe('completed')
    expect(pollingDecision('failed')).toBe('failed')
    expect(pollingDecision('cancelled')).toBe('unexpected')
  })
})
