import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
  vi.resetModules()
})

describe('api url resolution', () => {
  it('uses the configured API base URL when present', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.vigilweave.com/')

    const { getApiBaseUrl } = await import('./api-url')

    expect(getApiBaseUrl()).toBe('https://api.vigilweave.com')
  })

  it('falls back to the production API host on the app domain', async () => {
    vi.stubEnv('VITE_APP_URL', 'https://app.vigilweave.com')
    vi.stubGlobal('window', {
      location: {
        origin: 'https://app.vigilweave.com',
      },
    })

    const { getApiBaseUrl } = await import('./api-url')

    expect(getApiBaseUrl()).toBe('https://api.vigilweave.com')
  })

  it('uses the current origin for local unified deployments', async () => {
    vi.stubGlobal('window', {
      location: {
        origin: 'http://localhost:5173',
      },
    })

    const { getApiBaseUrl } = await import('./api-url')

    expect(getApiBaseUrl()).toBe('http://localhost:5173')
  })
})
