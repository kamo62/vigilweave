export function getApiBaseUrl(): string {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()
  if (configuredBaseUrl) {
    return configuredBaseUrl.replace(/\/$/, '')
  }

  const appUrl = import.meta.env.VITE_APP_URL?.trim().replace(/\/$/, '')
  if (appUrl && typeof window !== 'undefined' && window.location.origin === appUrl) {
    return 'https://api.vigilweave.com'
  }

  if (typeof window !== 'undefined') {
    return window.location.origin
  }
  return ''
}

export function buildApiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) {
    return path
  }
  return `${getApiBaseUrl()}${path}`
}
