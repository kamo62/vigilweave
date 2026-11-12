import { afterEach, describe, expect, it, vi } from 'vitest'

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
  vi.resetModules()
})

describe('domain routing', () => {
  it('redirects unknown origins to the configured app domain with search and hash intact', async () => {
    vi.stubGlobal('window', {
      location: {
        origin: 'https://vw205ba0c1web.z16.web.core.windows.net',
      },
    })
    vi.stubGlobal('location', globalThis.window.location)

    vi.stubEnv('VITE_MARKETING_URL', 'https://vigilweave.com')
    vi.stubEnv('VITE_APP_URL', 'https://app.vigilweave.com')

    const { getCrossDomainRedirect } = await import('./domain')

    expect(
      getCrossDomainRedirect('/login', {
        origin: 'https://vw205ba0c1web.z16.web.core.windows.net',
        marketingUrl: 'https://vigilweave.com',
        appUrl: 'https://app.vigilweave.com',
        search: '?next=%2Fprojects%2Facme',
        hash: '#section',
      }),
    ).toBe('https://app.vigilweave.com/login?next=%2Fprojects%2Facme#section')
  })

  it('redirects app routes away from the marketing origin', async () => {
    vi.stubGlobal('window', {
      location: {
        origin: 'https://vigilweave.com',
      },
    })
    vi.stubGlobal('location', globalThis.window.location)

    vi.stubEnv('VITE_MARKETING_URL', 'https://vigilweave.com')
    vi.stubEnv('VITE_APP_URL', 'https://app.vigilweave.com')

    const { getCrossDomainRedirect } = await import('./domain')

    expect(
      getCrossDomainRedirect('/projects/acme', {
        origin: 'https://vigilweave.com',
        marketingUrl: 'https://vigilweave.com',
        appUrl: 'https://app.vigilweave.com',
      }),
    ).toBe('https://app.vigilweave.com/projects/acme')
  })

  it('does not redirect unified deployments', async () => {
    vi.stubGlobal('window', {
      location: {
        origin: 'http://localhost:5173',
      },
    })
    vi.stubGlobal('location', globalThis.window.location)

    vi.unstubAllEnvs()

    const { getCrossDomainRedirect } = await import('./domain')

    expect(
      getCrossDomainRedirect('/projects', {
        origin: 'http://localhost:5173',
      }),
    ).toBeNull()
  })
})
