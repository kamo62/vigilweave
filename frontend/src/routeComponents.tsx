import { Suspense, lazy, type ComponentType } from 'react'

type RoutePage = ComponentType

function RoutePendingState() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <div className="w-full max-w-md space-y-4 rounded-sm border border-border bg-card/80 p-6 shadow-sm">
        <div className="h-3 w-24 animate-pulse rounded-full bg-muted" />
        <div className="h-10 w-3/4 animate-pulse rounded-sm bg-muted" />
        <div className="space-y-2">
          <div className="h-4 w-full animate-pulse rounded-full bg-muted" />
          <div className="h-4 w-5/6 animate-pulse rounded-full bg-muted" />
          <div className="h-4 w-2/3 animate-pulse rounded-full bg-muted" />
        </div>
      </div>
    </div>
  )
}

function RouteSuspense({ Component }: { Component: RoutePage }) {
  return (
    <Suspense fallback={<RoutePendingState />}>
      <Component />
    </Suspense>
  )
}

const LazyProjectsPage = lazy(() =>
  import('./pages/ProjectsPage').then((module) => ({ default: module.ProjectsPage })),
)

const LazyProjectDetailPage = lazy(() =>
  import('./pages/ProjectDetailPage').then((module) => ({ default: module.ProjectDetailPage })),
)

const LazyScansPage = lazy(() =>
  import('./pages/ScansPage').then((module) => ({ default: module.ScansPage })),
)

const LazyNewScanPage = lazy(() =>
  import('./pages/NewScanPage').then((module) => ({ default: module.NewScanPage })),
)

const LazyScanDetailPage = lazy(() =>
  import('./pages/ScanDetailPage').then((module) => ({ default: module.ScanDetailPage })),
)

const LazyIntegrationsPage = lazy(() =>
  import('./pages/IntegrationsPage').then((module) => ({ default: module.IntegrationsPage })),
)

const LazyPoliciesPage = lazy(() =>
  import('./pages/PoliciesPage').then((module) => ({ default: module.PoliciesPage })),
)

const LazySettingsPage = lazy(() =>
  import('./pages/SettingsPage').then((module) => ({ default: module.SettingsPage })),
)

const LazyLandingPage = lazy(() =>
  import('./pages/LandingPage').then((module) => ({ default: module.LandingPage })),
)

const LazyPricingPage = lazy(() =>
  import('./pages/PricingPage').then((module) => ({ default: module.PricingPage })),
)

const LazyTermsPage = lazy(() =>
  import('./pages/TermsPage').then((module) => ({ default: module.TermsPage })),
)

const LazyPrivacyPage = lazy(() =>
  import('./pages/PrivacyPage').then((module) => ({ default: module.PrivacyPage })),
)

const LazyRefundPolicyPage = lazy(() =>
  import('./pages/RefundPolicyPage').then((module) => ({ default: module.RefundPolicyPage })),
)

const LazyAuthCallbackPage = lazy(() =>
  import('./pages/AuthCallbackPage').then((module) => ({ default: module.AuthCallbackPage })),
)

const LazyLoginPage = lazy(() =>
  import('./pages/LoginPage').then((module) => ({ default: module.LoginPage })),
)

const LazyOnboardingPage = lazy(() =>
  import('./pages/OnboardingPage').then((module) => ({ default: module.OnboardingPage })),
)

const LazySetupPage = lazy(() =>
  import('./pages/SetupPage').then((module) => ({ default: module.SetupPage })),
)

const LazyDocsPage = lazy(() =>
  import('./pages/DocsPage').then((module) => ({ default: module.DocsPage })),
)

export function ProjectsRoutePage() {
  return <RouteSuspense Component={LazyProjectsPage} />
}

export function ProjectDetailRoutePage() {
  return <RouteSuspense Component={LazyProjectDetailPage} />
}

export function ScansRoutePage() {
  return <RouteSuspense Component={LazyScansPage} />
}

export function NewScanRoutePage() {
  return <RouteSuspense Component={LazyNewScanPage} />
}

export function ScanDetailRoutePage() {
  return <RouteSuspense Component={LazyScanDetailPage} />
}

export function IntegrationsRoutePage() {
  return <RouteSuspense Component={LazyIntegrationsPage} />
}

export function PoliciesRoutePage() {
  return <RouteSuspense Component={LazyPoliciesPage} />
}

export function SettingsRoutePage() {
  return <RouteSuspense Component={LazySettingsPage} />
}

export function LandingRoutePage() {
  return <RouteSuspense Component={LazyLandingPage} />
}

export function PricingRoutePage() {
  return <RouteSuspense Component={LazyPricingPage} />
}

export function TermsRoutePage() {
  return <RouteSuspense Component={LazyTermsPage} />
}

export function PrivacyRoutePage() {
  return <RouteSuspense Component={LazyPrivacyPage} />
}

export function RefundPolicyRoutePage() {
  return <RouteSuspense Component={LazyRefundPolicyPage} />
}

export function AuthCallbackRoutePage() {
  return <RouteSuspense Component={LazyAuthCallbackPage} />
}

export function LoginRoutePage() {
  return <RouteSuspense Component={LazyLoginPage} />
}

export function OnboardingRoutePage() {
  return <RouteSuspense Component={LazyOnboardingPage} />
}

export function SetupRoutePage() {
  return <RouteSuspense Component={LazySetupPage} />
}

export function DocsRoutePage() {
  return <RouteSuspense Component={LazyDocsPage} />
}
