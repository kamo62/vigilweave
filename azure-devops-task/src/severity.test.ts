import { describe, expect, test } from 'bun:test'

import { normalizeSeverity } from './severity'

describe('normalizeSeverity', () => {
  test('maps alternate casing and blocker values', () => {
    expect(normalizeSeverity('critical')).toBe('Critical')
    expect(normalizeSeverity('BLOCKER')).toBe('Critical')
    expect(normalizeSeverity('warning')).toBe('Medium')
  })
})
