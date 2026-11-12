export function buildCurrentAppPath(): string {
  if (typeof window === 'undefined') {
    return '/projects'
  }

  return `${window.location.pathname}${window.location.search}${window.location.hash}` || '/projects'
}

export function normalizeNextPath(value: unknown, fallback = '/projects'): string {
  if (typeof value !== 'string') {
    return fallback
  }

  const trimmed = value.trim()
  if (!trimmed.startsWith('/') || trimmed.startsWith('//')) {
    return fallback
  }

  if (
    trimmed === '/login' ||
    trimmed === '/signup' ||
    trimmed === '/setup' ||
    trimmed.startsWith('/auth/callback') ||
    trimmed.startsWith('/onboarding')
  ) {
    return fallback
  }

  return trimmed
}

export function buildLoginPath(options?: {
  nextPath?: string | null
  inviteToken?: string | null
}): string {
  const params = new URLSearchParams()
  const nextPath = normalizeNextPath(options?.nextPath, '')
  const inviteToken = typeof options?.inviteToken === 'string' ? options.inviteToken.trim() : ''

  if (nextPath) {
    params.set('next', nextPath)
  }

  if (inviteToken) {
    params.set('invite', inviteToken)
  }

  const query = params.toString()
  return query ? `/login?${query}` : '/login'
}
