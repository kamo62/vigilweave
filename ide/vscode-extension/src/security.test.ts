import { describe, expect, test } from 'bun:test'

import {
  apiUrl,
  assertTrustedWorkspace,
  readBoundApiKey,
  serviceOrigin,
} from './security'

describe('VigilWeave service security boundaries', () => {
  test('allows loopback HTTP and requires HTTPS for remote services', () => {
    expect(serviceOrigin('http://localhost:8000/vigilweave')).toBe('http://localhost:8000')
    expect(() => serviceOrigin('http://example.com')).toThrow('HTTPS')
    expect(() => serviceOrigin('file:///tmp/api')).toThrow('HTTP or HTTPS')
  })

  test('keeps reverse-proxy prefixes when constructing API URLs', () => {
    expect(apiUrl('https://scanner.example.com/proxy/v1', '/api/v1/ide/analyze').toString())
      .toBe('https://scanner.example.com/proxy/v1/api/v1/ide/analyze')
  })

  test('binds a stored API key to its server origin and rejects legacy keys', () => {
    const boundKey = JSON.stringify({ apiKey: 'vw_test', origin: 'https://scanner.example.com' })
    expect(readBoundApiKey(boundKey, 'https://scanner.example.com/proxy')).toBe('vw_test')
    expect(() => readBoundApiKey(boundKey, 'https://other.example.com'))
      .toThrow('Re-enter your API key')
    expect(() => readBoundApiKey('legacy-key', 'https://scanner.example.com'))
      .toThrow('Re-enter your API key')
  })

  test('blocks scans and git operations in an untrusted workspace', () => {
    expect(() => assertTrustedWorkspace(false)).toThrow('trusted workspace')
    expect(() => assertTrustedWorkspace(true)).not.toThrow()
  })
})
