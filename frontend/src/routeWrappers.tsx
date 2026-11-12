import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { useNavigate } from '@tanstack/react-router'

import { Layout } from './components/Layout'
import { Button } from './components/ui/button'
import { PublicLayout } from './layouts/PublicLayout'
import { getDomainContext } from './lib/domain'
import { buildCurrentAppPath, normalizeNextPath } from './lib/navigation'
import { useAuth } from './lib/useAuth'
import {
  AuthCallbackRoutePage,
  DocsRoutePage,
  IntegrationsRoutePage,
  LandingRoutePage,
  LoginRoutePage,
  NewScanRoutePage,
  OnboardingRoutePage,
  PoliciesRoutePage,
  PrivacyRoutePage,
  PricingRoutePage,
  ProjectDetailRoutePage,
  RefundPolicyRoutePage,
  ProjectsRoutePage,
  ScanDetailRoutePage,
  ScansRoutePage,
  SettingsRoutePage,
  SetupRoutePage,
  TermsRoutePage,
} from './routeComponents'

function RouteStatus({
  actionLabel,
  message,
  onAction,
}: {
  actionLabel?: string
  message: string
  onAction?: () => void
}) {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center text-muted-foreground text-sm space-y-3">
        <div>{message}</div>
        {actionLabel && onAction ? (
          <Button size="sm" variant="flat" onClick={onAction}>
            {actionLabel}
          </Button>
        ) : null}
      </div>
    </div>
  )
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const {
    authBootstrapError,
    isAuthenticated,
    isLoading,
    login,
    refreshCapabilities,
    sessionAuthProvider,
  } = useAuth()
  const nextPath = buildCurrentAppPath()

  useEffect(() => {
    if (
      !isLoading &&
      !authBootstrapError &&
      sessionAuthProvider !== null &&
      sessionAuthProvider !== 'none' &&
      !isAuthenticated
    ) {
      login({ nextPath })
    }
  }, [authBootstrapError, isAuthenticated, isLoading, login, nextPath, sessionAuthProvider])

  if (authBootstrapError) {
    return (
      <RouteStatus
        actionLabel="Retry"
        message="Authentication could not be initialized. Retry once the API is reachable."
        onAction={() => void refreshCapabilities()}
      />
    )
  }

  if (isLoading || sessionAuthProvider === null) {
    return <RouteStatus message="Loading..." />
  }

  if (sessionAuthProvider === 'none') {
    return <>{children}</>
  }

  if (!isAuthenticated) {
    return <RouteStatus message="Redirecting to login..." />
  }

  return <>{children}</>
}

function RequireOnboarding({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const { isLoading, sessionAuthProvider, user } = useAuth()
  const nextPath = normalizeNextPath(buildCurrentAppPath())

  useEffect(() => {
    if (
      !isLoading &&
      sessionAuthProvider === 'workos' &&
      user &&
      !user.onboarding_completed
    ) {
      void navigate({
        to: '/onboarding',
        search: {
          repoMode: undefined,
          githubAppConnected: undefined,
          githubAppMessage: undefined,
          next: nextPath,
        },
        replace: true,
      })
    }
  }, [isLoading, navigate, nextPath, sessionAuthProvider, user])

  if (sessionAuthProvider === 'workos' && user && !user.onboarding_completed) {
    return <RouteStatus message="Redirecting to onboarding..." />
  }

  return <>{children}</>
}

function ProtectedLayout({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <RequireOnboarding>
        <Layout>{children}</Layout>
      </RequireOnboarding>
    </RequireAuth>
  )
}

export function LandingPageWrapper() {
  const navigate = useNavigate()
  const { authBootstrapError, isAuthenticated, isLoading, refreshCapabilities, saasEnabled } = useAuth()
  const domainContext = getDomainContext()

  useEffect(() => {
    if (domainContext === 'marketing') {
      return
    }
    if (!isLoading && !authBootstrapError && (!saasEnabled || isAuthenticated)) {
      void navigate({ to: '/projects', replace: true })
    }
  }, [authBootstrapError, domainContext, isAuthenticated, isLoading, navigate, saasEnabled])

  if (domainContext === 'marketing') {
    return (
      <PublicLayout>
        <LandingRoutePage />
      </PublicLayout>
    )
  }

  if (authBootstrapError) {
    return (
      <RouteStatus
        actionLabel="Retry"
        message="Authentication could not be initialized. Retry once the API is reachable."
        onAction={() => void refreshCapabilities()}
      />
    )
  }

  if (isLoading || !saasEnabled || isAuthenticated) {
    return <RouteStatus message={!saasEnabled ? 'Opening workspace...' : 'Loading...'} />
  }

  return (
    <PublicLayout>
      <LandingRoutePage />
    </PublicLayout>
  )
}

export function PricingPageWrapper() {
  return (
    <PublicLayout>
      <PricingRoutePage />
    </PublicLayout>
  )
}

export function TermsPageWrapper() {
  return (
    <PublicLayout>
      <TermsRoutePage />
    </PublicLayout>
  )
}

export function PrivacyPageWrapper() {
  return (
    <PublicLayout>
      <PrivacyRoutePage />
    </PublicLayout>
  )
}

export function RefundPolicyPageWrapper() {
  return (
    <PublicLayout>
      <RefundPolicyRoutePage />
    </PublicLayout>
  )
}

export function DocsPageWrapper() {
  return (
    <PublicLayout>
      <DocsRoutePage />
    </PublicLayout>
  )
}

export function AuthCallbackPageWrapper() {
  return <AuthCallbackRoutePage />
}

function AuthEntryPageWrapper({ mode }: { mode: 'login' | 'signup' }) {
  const navigate = useNavigate()
  const {
    authBootstrapError,
    bootstrapRegistrationRequired,
    isAuthenticated,
    isLoading,
    login,
    refreshCapabilities,
    saasEnabled,
    sessionAuthProvider,
    workosConfigured,
  } = useAuth()
  const routeSearch = window.location.search
    ? new URLSearchParams(window.location.search)
    : new URLSearchParams()
  const nextPath = normalizeNextPath(routeSearch.get('next'), '/projects')
  const inviteToken = routeSearch.get('invite')?.trim() || undefined

  useEffect(() => {
    if (isLoading) {
      return
    }
    if (authBootstrapError) {
      return
    }
    if (isAuthenticated) {
      window.location.replace(nextPath)
      return
    }
    if (sessionAuthProvider === 'workos') {
      login({ nextPath, inviteToken })
      return
    }
    if (sessionAuthProvider === 'local' && mode === 'signup' && !bootstrapRegistrationRequired) {
      void navigate({ to: '/login', search: { next: nextPath, invite: inviteToken }, replace: true })
      return
    }
    if (sessionAuthProvider === 'none') {
      window.location.replace(nextPath)
      return
    }
  }, [
    authBootstrapError,
    bootstrapRegistrationRequired,
    inviteToken,
    isAuthenticated,
    isLoading,
    login,
    mode,
    navigate,
    nextPath,
    sessionAuthProvider,
  ])

  if (authBootstrapError) {
    return (
      <RouteStatus
        actionLabel="Retry"
        message="Authentication could not be initialized. Retry once the API is reachable."
        onAction={() => void refreshCapabilities()}
      />
    )
  }

  if (sessionAuthProvider === 'local') {
    return (
      <PublicLayout>
        {mode === 'signup' && bootstrapRegistrationRequired ? (
          <SetupRoutePage />
        ) : (
          <LoginRoutePage />
        )}
      </PublicLayout>
    )
  }

  const message =
    !saasEnabled || !workosConfigured
      ? 'Opening workspace...'
      : `Redirecting to ${mode === 'signup' ? 'sign up' : 'sign in'}...`

  return <RouteStatus message={message} />
}

export function LoginPageWrapper() {
  return <AuthEntryPageWrapper mode="login" />
}

export function SignupPageWrapper() {
  return <AuthEntryPageWrapper mode="signup" />
}

export function SetupPageWrapper() {
  const navigate = useNavigate()
  const {
    authBootstrapError,
    bootstrapRegistrationRequired,
    isAuthenticated,
    isLoading,
    refreshCapabilities,
    sessionAuthProvider,
  } = useAuth()
  const routeSearch = window.location.search ? new URLSearchParams(window.location.search) : new URLSearchParams()
  const nextPath = normalizeNextPath(routeSearch.get('next'), '/projects')

  useEffect(() => {
    if (isLoading) {
      return
    }
    if (authBootstrapError) {
      return
    }
    if (isAuthenticated) {
      window.location.replace(nextPath)
      return
    }
    if (sessionAuthProvider !== 'local') {
      void navigate({
        to: '/login',
        search: { next: nextPath, invite: undefined },
        replace: true,
      })
      return
    }
    if (!bootstrapRegistrationRequired) {
      void navigate({
        to: '/login',
        search: { next: nextPath, invite: undefined },
        replace: true,
      })
    }
  }, [
    authBootstrapError,
    bootstrapRegistrationRequired,
    isAuthenticated,
    isLoading,
    navigate,
    nextPath,
    refreshCapabilities,
    sessionAuthProvider,
  ])

  if (authBootstrapError) {
    return (
      <RouteStatus
        actionLabel="Retry"
        message="Authentication could not be initialized. Retry once the API is reachable."
        onAction={() => void refreshCapabilities()}
      />
    )
  }

  return (
    <PublicLayout>
      <SetupRoutePage />
    </PublicLayout>
  )
}

export function ProjectsPageWrapper() {
  return (
    <ProtectedLayout>
      <ProjectsRoutePage />
    </ProtectedLayout>
  )
}

export function ProjectDetailPageWrapper() {
  return (
    <ProtectedLayout>
      <ProjectDetailRoutePage />
    </ProtectedLayout>
  )
}

export function ScansPageWrapper() {
  return (
    <ProtectedLayout>
      <ScansRoutePage />
    </ProtectedLayout>
  )
}

export function NewScanPageWrapper() {
  return (
    <ProtectedLayout>
      <NewScanRoutePage />
    </ProtectedLayout>
  )
}

export function ScanDetailPageWrapper() {
  return (
    <ProtectedLayout>
      <ScanDetailRoutePage />
    </ProtectedLayout>
  )
}

export function IntegrationsPageWrapper() {
  return (
    <ProtectedLayout>
      <IntegrationsRoutePage />
    </ProtectedLayout>
  )
}

export function PoliciesPageWrapper() {
  return (
    <ProtectedLayout>
      <PoliciesRoutePage />
    </ProtectedLayout>
  )
}

export function SettingsPageWrapper() {
  return (
    <ProtectedLayout>
      <SettingsRoutePage />
    </ProtectedLayout>
  )
}

export function OnboardingPageWrapper() {
  const navigate = useNavigate()
  const { isLoading, sessionAuthProvider } = useAuth()

  useEffect(() => {
    if (!isLoading && sessionAuthProvider !== 'workos') {
      void navigate({ to: '/projects', replace: true })
    }
  }, [isLoading, navigate, sessionAuthProvider])

  return (
    <RequireAuth>
      <OnboardingRoutePage />
    </RequireAuth>
  )
}
