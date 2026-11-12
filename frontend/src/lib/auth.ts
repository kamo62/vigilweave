const API_KEY_STORAGE_KEY = 'vigilweave_api_key'
const TENANT_STORAGE_KEY = 'vigilweave_tenant'
const CSRF_TOKEN_STORAGE_KEY = 'vigilweave_csrf_token'

export interface RuntimeAuthConfig {
  apiKey: string
  tenant: string
}

function readStorage(key: string): string {
  if (typeof window === 'undefined') {
    return ''
  }
  return (window.localStorage.getItem(key) ?? '').trim()
}

export function getRuntimeAuthConfig(): RuntimeAuthConfig {
  return {
    apiKey: readStorage(API_KEY_STORAGE_KEY),
    tenant: readStorage(TENANT_STORAGE_KEY),
  }
}

export function setRuntimeAuthConfig(config: Partial<RuntimeAuthConfig>): void {
  if (typeof window === 'undefined') {
    return
  }
  if (config.apiKey !== undefined) {
    const value = config.apiKey.trim()
    if (value) {
      window.localStorage.setItem(API_KEY_STORAGE_KEY, value)
    } else {
      window.localStorage.removeItem(API_KEY_STORAGE_KEY)
    }
  }
  if (config.tenant !== undefined) {
    const value = config.tenant.trim()
    if (value) {
      window.localStorage.setItem(TENANT_STORAGE_KEY, value)
    } else {
      window.localStorage.removeItem(TENANT_STORAGE_KEY)
    }
  }
}

export function clearRuntimeAuthConfig(): void {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.removeItem(API_KEY_STORAGE_KEY)
  window.localStorage.removeItem(TENANT_STORAGE_KEY)
}

export function getAuthHeaders(): Record<string, string> {
  const runtime = getRuntimeAuthConfig()
  const apiKey = runtime.apiKey
  const tenant = runtime.tenant
  const headers: Record<string, string> = {}
  if (apiKey) {
    headers.Authorization = `Bearer ${apiKey}`
  }
  if (tenant) {
    headers['X-VigilWeave-Tenant'] = tenant
  }
  return headers
}

export function getCsrfToken(): string {
  if (typeof window === 'undefined') {
    return ''
  }
  return (window.sessionStorage.getItem(CSRF_TOKEN_STORAGE_KEY) ?? '').trim()
}

export function setCsrfToken(token: string): void {
  if (typeof window === 'undefined') {
    return
  }
  const value = token.trim()
  if (value) {
    window.sessionStorage.setItem(CSRF_TOKEN_STORAGE_KEY, value)
  } else {
    window.sessionStorage.removeItem(CSRF_TOKEN_STORAGE_KEY)
  }
}
