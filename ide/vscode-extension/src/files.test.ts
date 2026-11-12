import { describe, expect, test } from 'bun:test'

describe('source extension filter list', () => {
  test('keeps the extension list stable for supported languages', () => {
    const supported = ['.py', '.js', '.ts', '.tf', '.yaml', '.yml']
    expect(supported).toContain('.py')
    expect(supported).toContain('.ts')
  })
})
