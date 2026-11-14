export function serviceOrigin(rawUrl: string): string {
  return parseServiceUrl(rawUrl).origin
}

export function apiUrl(baseUrl: string, endpoint: string): URL {
  const base = parseServiceUrl(baseUrl)
  if (!base.pathname.endsWith('/')) base.pathname += '/'
  return new URL(endpoint.replace(/^\/+/, ''), base)
}

export function readBoundApiKey(storedValue: string, serverUrl: string): string {
  const reenterMessage = 'Re-enter your API key for the selected VigilWeave server.'
  let stored: unknown
  try {
    stored = JSON.parse(storedValue)
  } catch {
    throw new Error(reenterMessage)
  }

  if (
    typeof stored !== 'object' ||
    stored === null ||
    !('apiKey' in stored) ||
    typeof stored.apiKey !== 'string' ||
    !stored.apiKey ||
    !('origin' in stored) ||
    typeof stored.origin !== 'string' ||
    stored.origin !== serviceOrigin(serverUrl)
  ) {
    throw new Error(reenterMessage)
  }

  return stored.apiKey
}

export function assertTrustedWorkspace(isTrusted: boolean): void {
  if (!isTrusted) {
    throw new Error(
      'VigilWeave scans are disabled in untrusted workspaces. Mark this workspace as trusted to upload files or run Git commands.',
    )
  }
}

function parseServiceUrl(rawUrl: string): URL {
  let url: URL
  try {
    url = new URL(rawUrl)
  } catch {
    throw new Error('VigilWeave server and dashboard URLs must be valid HTTP or HTTPS URLs.')
  }

  if (url.protocol !== 'http:' && url.protocol !== 'https:') {
    throw new Error('VigilWeave server and dashboard URLs must use HTTP or HTTPS.')
  }
  if (url.username || url.password) {
    throw new Error('VigilWeave server and dashboard URLs must not contain credentials.')
  }
  if (url.protocol === 'http:' && !isLoopback(url.hostname)) {
    throw new Error('VigilWeave server and dashboard URLs must use HTTPS outside loopback development.')
  }

  return url
}

function isLoopback(hostname: string): boolean {
  const host = hostname.toLowerCase().replace(/^\[|\]$/g, '')
  return (
    host === 'localhost' ||
    host.endsWith('.localhost') ||
    host === '::1' ||
    /^127(?:\.\d{1,3}){3}$/.test(host)
  )
}
