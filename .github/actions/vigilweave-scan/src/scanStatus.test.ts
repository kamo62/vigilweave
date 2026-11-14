import { describe, expect, test } from 'bun:test'

import { pollingDecision } from './scanStatus'

describe('pollingDecision', () => {
  test('keeps polling only known nonterminal states', () => {
    expect(pollingDecision('queued')).toBe('pending')
    expect(pollingDecision('running')).toBe('pending')
    expect(pollingDecision('cancelled')).toBe('unexpected')
  })
})
