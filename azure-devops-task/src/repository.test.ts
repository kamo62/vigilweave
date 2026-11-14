import { describe, expect, test } from 'bun:test'

import { sanitizeRepositoryUrl } from './repository'

describe('sanitizeRepositoryUrl', () => {
  test('rejects malformed URLs without returning or exposing credentials', () => {
    expect(() => sanitizeRepositoryUrl('https://build:synthetic@[invalid/repo'))
      .toThrow('Repository URL must be valid')
  })
  test('removes embedded credentials before a repository URL is sent to VigilWeave', () => {
    expect(sanitizeRepositoryUrl('https://build:secret@dev.azure.com/org/project/_git/repo'))
      .toBe('https://dev.azure.com/org/project/_git/repo')
  })
})
