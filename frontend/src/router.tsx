import { Outlet, createRootRoute, createRoute, createRouter, redirect } from '@tanstack/react-router'

import { AuthProvider } from './lib/auth-context'
import { getCrossDomainRedirect } from './lib/domain'
import {
  AuthCallbackPageWrapper,
  DocsPageWrapper,
  IntegrationsPageWrapper,
  LandingPageWrapper,
  LoginPageWrapper,
  NewScanPageWrapper,
  OnboardingPageWrapper,
  PoliciesPageWrapper,
  PrivacyPageWrapper,
  PricingPageWrapper,
  ProjectDetailPageWrapper,
  RefundPolicyPageWrapper,
  ProjectsPageWrapper,
  ScanDetailPageWrapper,
  ScansPageWrapper,
  SettingsPageWrapper,
  SetupPageWrapper,
  SignupPageWrapper,
  TermsPageWrapper,
} from './routeWrappers'

// Root route with AuthProvider and cross-domain redirect
const rootRoute = createRootRoute({
  beforeLoad: ({ location }) => {
    const redirectUrl = getCrossDomainRedirect(location.pathname, {
      search: location.searchStr,
      hash: location.hash,
    })
    if (redirectUrl) {
      // Full cross-domain redirect (not a TanStack redirect — we need
      // to leave the current origin entirely).
      window.location.replace(redirectUrl)
      // Throw to abort the current navigation while the browser redirects.
      throw redirect({ to: '/' })
    }
  },
  component: function Root() {
    return (
      <AuthProvider>
        <Outlet />
      </AuthProvider>
    )
  },
})

const landingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: LandingPageWrapper,
})

const pricingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/pricing',
  component: PricingPageWrapper,
})

const termsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/terms',
  component: TermsPageWrapper,
})

const privacyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/privacy',
  component: PrivacyPageWrapper,
})

const refundPolicyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/refund-policy',
  component: RefundPolicyPageWrapper,
})

const docsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/docs',
  component: DocsPageWrapper,
  validateSearch: (search: Record<string, unknown>): { section?: string } => ({
    section: search.section ? String(search.section) : undefined,
  }),
})

const authCallbackRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/auth/callback',
  component: AuthCallbackPageWrapper,
  validateSearch: (search: Record<string, unknown>) => ({
    error: search.error ? String(search.error) : undefined,
    error_description: search.error_description ? String(search.error_description) : undefined,
  }),
})

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: LoginPageWrapper,
  validateSearch: (search: Record<string, unknown>) => ({
    next: search.next ? String(search.next) : undefined,
    invite: search.invite ? String(search.invite) : undefined,
  }),
})

const signupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/signup',
  component: SignupPageWrapper,
  validateSearch: (search: Record<string, unknown>) => ({
    next: search.next ? String(search.next) : undefined,
    invite: search.invite ? String(search.invite) : undefined,
  }),
})

const setupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/setup',
  component: SetupPageWrapper,
  validateSearch: (search: Record<string, unknown>) => ({
    next: search.next ? String(search.next) : undefined,
  }),
})

const projectsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/projects',
  component: ProjectsPageWrapper,
})

const projectDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/projects/$projectKey',
  component: ProjectDetailPageWrapper,
})

const scansRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/scans',
  component: ScansPageWrapper,
})

const newScanRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/scans/new',
  component: NewScanPageWrapper,
  validateSearch: (search: Record<string, unknown>) => ({
    repo: (search.repo as string) ?? '',
    projectKey: (search.projectKey as string) ?? '',
  }),
})

const scanDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/scans/$scanId',
  component: ScanDetailPageWrapper,
})

const integrationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/integrations',
  component: IntegrationsPageWrapper,
})

const policiesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/policies',
  component: PoliciesPageWrapper,
})

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  component: SettingsPageWrapper,
  validateSearch: (search: Record<string, unknown>) => ({
    tab: search.tab ? String(search.tab) : undefined,
  }),
})

const onboardingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/onboarding',
  component: OnboardingPageWrapper,
  validateSearch: (search: Record<string, unknown>) => ({
    repoMode: search.repoMode ? String(search.repoMode) : undefined,
    githubAppConnected: search.githubAppConnected ? String(search.githubAppConnected) : undefined,
    githubAppMessage: search.githubAppMessage ? String(search.githubAppMessage) : undefined,
    next: search.next ? String(search.next) : undefined,
  }),
})

// Redirect old routes to new locations
const dashboardRedirect = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dashboard',
  beforeLoad: () => {
    throw redirect({ to: '/projects' })
  },
})

const routeTree = rootRoute.addChildren([
  landingRoute,
  pricingRoute,
  termsRoute,
  privacyRoute,
  refundPolicyRoute,
  docsRoute,
  authCallbackRoute,
  loginRoute,
  signupRoute,
  setupRoute,
  projectsRoute,
  projectDetailRoute,
  scansRoute,
  newScanRoute,
  scanDetailRoute,
  integrationsRoute,
  policiesRoute,
  settingsRoute,
  onboardingRoute,
  dashboardRedirect,
])

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
