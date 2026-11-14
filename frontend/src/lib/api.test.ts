import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const CSRF_STORAGE_KEY = 'vigilweave_csrf_token'

function installFetchMock(
  handler: (request: Request) => Promise<Response>,
): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : new Request(input, init)
    return handler(request)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

beforeEach(() => {
  vi.resetModules()
  vi.stubEnv('VITE_API_BASE_URL', 'http://api.test')
  sessionStorage.clear()
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

describe('API mutation transport', () => {
  it('retries a CSRF-rejected Request with its original body and refreshed token', async () => {
    sessionStorage.setItem(CSRF_STORAGE_KEY, 'stale-token')
    const attempts: Array<{ csrf: string | null; body: string }> = []
    const fetchMock = installFetchMock(async (request) => {
      const url = new URL(request.url)
      if (url.pathname === '/api/v1/auth/csrf') {
        return new Response(JSON.stringify({ csrf_token: 'fresh-token' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      const body = await request.text()
      attempts.push({ csrf: request.headers.get('X-CSRF-Token'), body })
      if (attempts.length === 1) {
        return new Response(JSON.stringify({ detail: 'CSRF token required' }), {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      return new Response(JSON.stringify({ id: 1, key: 'demo', name: 'Demo' }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      })
    })

    const { createProject } = await import('./api')
    await createProject({
      key: 'demo',
      name: 'Demo',
      default_branch: 'main',
    })

    expect(attempts).toHaveLength(2)
    expect(attempts[0]?.csrf).toBe('stale-token')
    expect(attempts[1]?.csrf).toBe('fresh-token')
    expect(attempts[1]?.body).toBe(attempts[0]?.body)
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('does not retry a mutation rejected for authorization', async () => {
    sessionStorage.setItem(CSRF_STORAGE_KEY, 'valid-token')
    const mutationRequests: Request[] = []
    const fetchMock = installFetchMock(async (request) => {
      const url = new URL(request.url)
      if (url.pathname.endsWith('/reassign')) {
        mutationRequests.push(request)
        return new Response(JSON.stringify({ detail: 'Tenant administrator required' }), {
          status: 403,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      throw new Error(`Unexpected request to ${url.pathname}`)
    })

    const { reassignGitHubAppLinkedRepos } = await import('./api')
    await expect(
      reassignGitHubAppLinkedRepos(12, { target_scm_connection_id: 4 }),
    ).rejects.toThrow('Tenant administrator required')

    expect(mutationRequests).toHaveLength(1)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('accepts 204 responses from shared delete requests', async () => {
    sessionStorage.setItem(CSRF_STORAGE_KEY, 'valid-token')
    const fetchMock = installFetchMock(async (request) => {
      expect(request.method).toBe('DELETE')
      return new Response(null, { status: 204 })
    })

    const { deleteSCMConnection } = await import('./api')
    await expect(deleteSCMConnection(4)).resolves.toBeUndefined()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
