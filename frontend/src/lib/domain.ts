/**
 * Domain-aware routing for the vigilweave.com / app.vigilweave.com split.
 *
 * In SaaS mode the marketing site (landing, pricing, docs) lives on
 * vigilweave.com while the authenticated application lives on
 * app.vigilweave.com.  Self-hosted deployments serve everything from
 * a single origin (no split).
 *
 * Environment variables:
 *   VITE_MARKETING_URL  – e.g. "https://vigilweave.com"
 *   VITE_APP_URL        – e.g. "https://app.vigilweave.com"
 *
 * When neither variable is set the current origin is used for both,
 * which preserves the existing single-origin behaviour for self-hosted
 * and local development.
 */

function getMarketingUrlEnv(): string {
  return (import.meta.env.VITE_MARKETING_URL as string | undefined)?.replace(/\/$/, '') ?? ''
}

function getAppUrlEnv(): string {
  return (import.meta.env.VITE_APP_URL as string | undefined)?.replace(/\/$/, '') ?? ''
}

/** Routes that belong on the marketing site. */
const MARKETING_PATHS = new Set(['/', '/pricing', '/docs', '/terms', '/privacy', '/refund-policy'])

/** Routes that belong on the app site. */
const APP_PATH_PREFIXES = [
  '/projects',
  '/scans',
  '/integrations',
  '/policies',
  '/settings',
  '/onboarding',
]

export type DomainContext = 'marketing' | 'app' | 'unified'

interface DomainConfig {
  marketingUrl: string
  appUrl: string
}

interface RedirectOptions {
  origin?: string
  search?: string
  hash?: string
  marketingUrl?: string
  appUrl?: string
}

function getBrowserOrigin(): string | null {
  if (typeof window === 'undefined') return null
  return window.location.origin
}

function normalizeLocationSuffix(value: string | undefined, prefix: '?' | '#'): string {
  if (!value) return ''
  return value.startsWith(prefix) ? value : `${prefix}${value}`
}

function resolveDomainConfig(overrides: Pick<RedirectOptions, 'marketingUrl' | 'appUrl'> = {}): DomainConfig {
  return {
    marketingUrl: overrides.marketingUrl?.replace(/\/$/, '') ?? getMarketingUrlEnv(),
    appUrl: overrides.appUrl?.replace(/\/$/, '') ?? getAppUrlEnv(),
  }
}

function isConfiguredOrigin(origin: string, config: DomainConfig): boolean {
  const appUrlValue = config.appUrl
  const marketingUrlValue = config.marketingUrl
  return Boolean((appUrlValue && origin === appUrlValue) || (marketingUrlValue && origin === marketingUrlValue))
}

function targetUrlForPath(pathname: string, config: DomainConfig): string {
  for (const prefix of APP_PATH_PREFIXES) {
    if (pathname === prefix || pathname.startsWith(prefix + '/')) {
      return appUrl(pathname, config)
    }
  }

  if (pathname === '/login' || pathname === '/signup' || pathname === '/setup' || pathname === '/auth/callback') {
    return appUrl(pathname, config)
  }

  return marketingUrl(pathname, config)
}

/**
 * Detect which domain context the browser is currently on.
 *
 * Returns `'unified'` when no domain split is configured (self-hosted /
 * local dev) — in that case all routes are served from the same origin.
 */
export function getDomainContext(origin = getBrowserOrigin(), config = resolveDomainConfig()): DomainContext {
  const marketingUrlValue = config.marketingUrl
  const appUrlValue = config.appUrl

  if (!marketingUrlValue && !appUrlValue) return 'unified'
  if (!origin) return 'unified'

  // Exact match against configured URLs
  if (appUrlValue && origin === appUrlValue) return 'app'
  if (marketingUrlValue && origin === marketingUrlValue) return 'marketing'

  // If only one is configured, infer the other
  if (appUrlValue && !marketingUrlValue) return origin === appUrlValue ? 'app' : 'marketing'
  if (marketingUrlValue && !appUrlValue) return origin === marketingUrlValue ? 'marketing' : 'app'

  // Fall back to unified if we can't determine
  return 'unified'
}

/**
 * Build an absolute URL on the marketing site.
 * In unified mode returns a relative path.
 */
export function marketingUrl(path: string, config = resolveDomainConfig()): string {
  const marketingUrlValue = config.marketingUrl
  if (!marketingUrlValue) return path
  return `${marketingUrlValue}${path}`
}

/**
 * Build an absolute URL on the app site.
 * In unified mode returns a relative path.
 */
export function appUrl(path: string, config = resolveDomainConfig()): string {
  const appUrlValue = config.appUrl
  if (!appUrlValue) return path
  return `${appUrlValue}${path}`
}

/**
 * Check whether the current path should trigger a cross-domain redirect.
 *
 * Returns the full redirect URL if the user is on the wrong domain for the
 * given path, or `null` if no redirect is needed.
 */
export function getCrossDomainRedirect(pathname: string, options: RedirectOptions = {}): string | null {
  const origin = options.origin ?? getBrowserOrigin()
  const config = resolveDomainConfig(options)
  const splitEnabled = Boolean(config.marketingUrl || config.appUrl)
  if (!splitEnabled) return null

  let redirectTarget: string | null = null

  if (origin && !isConfiguredOrigin(origin, config)) {
    redirectTarget = targetUrlForPath(pathname, config)
  }

  const ctx = getDomainContext(origin, config)
  if (!redirectTarget && ctx === 'unified') return null

  if (!redirectTarget && ctx === 'marketing') {
    // On the marketing domain — redirect app routes to app.vigilweave.com
    for (const prefix of APP_PATH_PREFIXES) {
      if (pathname === prefix || pathname.startsWith(prefix + '/')) {
        redirectTarget = appUrl(pathname, config)
        break
      }
    }
    // Auth routes should also go to app
    if (!redirectTarget && (pathname === '/login' || pathname === '/signup' || pathname === '/setup' || pathname === '/auth/callback')) {
      redirectTarget = appUrl(pathname, config)
    }
  }

  if (!redirectTarget && ctx === 'app') {
    // On the app domain — redirect marketing routes to vigilweave.com
    if (MARKETING_PATHS.has(pathname) && config.marketingUrl) {
      redirectTarget = marketingUrl(pathname, config)
    }
  }

  if (!redirectTarget) return null

  return `${redirectTarget}${normalizeLocationSuffix(options.search, '?')}${normalizeLocationSuffix(options.hash, '#')}`
}

/** Whether the domain split is active (SaaS deployment). */
export function isDomainSplitEnabled(): boolean {
  const config = resolveDomainConfig()
  return Boolean(config.marketingUrl || config.appUrl)
}
