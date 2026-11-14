import { describe, expect, test } from 'bun:test'

import { resolveRepositoryUrl, sanitizeRepositoryUrl } from './repository'

describe('repository URL handling', () => {
  test('rejects malformed URLs without returning or exposing credentials', () => {
    expect(() => sanitizeRepositoryUrl('https://build:synthetic@[invalid/repo'))
      .toThrow('Repository URL must be valid')
  })
  test('turns the GitHub owner/repo default into a full clone URL on GitHub Enterprise', () => {
    expect(resolveRepositoryUrl('', 'acme/widget', 'https://github.example.com'))
      .toBe('https://github.example.com/acme/widget.git')
  })

  test('removes embedded credentials before sending an explicit repository URL', () => {
    expect(sanitizeRepositoryUrl('https://build:secret@git.example.com/acme/widget.git'))
      .toBe('https://git.example.com/acme/widget.git')
  })
})
