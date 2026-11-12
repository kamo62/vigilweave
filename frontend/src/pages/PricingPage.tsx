import { type JSX, useEffect, useMemo, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Button, Card, Chip } from '@heroui/react'
import { CheckCircle2, Download, Mail, ShieldCheck, ArrowRight } from 'lucide-react'

import { fetchBillingPublicConfig, type BillingPublicConfig } from '../lib/api'
import { useLicense } from '../lib/hooks/useLicense'
import { openPaddleOverlayCheckout } from '../lib/paddle'
import { DOWNLOADS_URL, SALES_EMAIL_URL, SUPPORT_EMAIL_URL } from '../lib/public-links'
import { useAuth } from '../lib/useAuth'

const comparisonRows = [
  { capability: 'Deployment Options', community: 'Self-hosted', pro: 'Hosted SaaS', enterprise: 'Full Portfolio Control', highlight: 'pro' },
  { capability: 'Identity Management', community: 'Local Auth', pro: 'OAuth 2.0', enterprise: 'SAML / SSO / SCIM', highlight: 'enterprise' },
  { capability: 'Policy Customization', community: '3 Presets', pro: 'Unlimited', enterprise: 'Global Sync Policies', highlight: '' },
  { capability: 'Integrations', community: 'GitHub Actions', pro: 'CI/CD Full Stack', enterprise: 'MCP Server + Custom API', highlight: 'enterprise' },
  { capability: 'Compliance Reporting', community: '—', pro: 'Standard Reports', enterprise: 'Audit-Ready Exports', highlight: 'enterprise' },
] as const

export function PricingPage(): JSX.Element {
  const { isAuthenticated, login, user } = useAuth()
  const { isCommunityDistribution } = useLicense()
  const navigate = useNavigate()
  const [billingConfig, setBillingConfig] = useState<BillingPublicConfig | null>(null)
  const [billingConfigLoaded, setBillingConfigLoaded] = useState(false)
  const [checkoutPending, setCheckoutPending] = useState(false)
  const [checkoutError, setCheckoutError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    void (async () => {
      try {
        const config = await fetchBillingPublicConfig()
        if (!cancelled) {
          setBillingConfig(config)
        }
      } catch (error) {
        console.error('Failed to load billing config:', error)
      } finally {
        if (!cancelled) {
          setBillingConfigLoaded(true)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [])

  const checkoutSuccess = useMemo(() => {
    if (typeof window === 'undefined') {
      return false
    }
    return new URLSearchParams(window.location.search).get('checkout') === 'success'
  }, [])

  const proCheckoutReady = Boolean(
    billingConfig?.checkout_ready && billingConfig.client_token && billingConfig.pro_price_id,
  )
  const proButtonLabel = !isAuthenticated
    ? isCommunityDistribution
      ? 'Commercial Distribution Only'
      : 'Sign In to Buy'
    : !billingConfigLoaded
      ? 'Loading Billing'
      : proCheckoutReady
        ? 'Start Pro Checkout'
        : isCommunityDistribution
          ? 'Commercial Distribution Only'
          : 'Paddle Setup Pending'
  const proButtonDisabled =
    isCommunityDistribution ||
    checkoutPending ||
    (isAuthenticated && billingConfigLoaded && !proCheckoutReady)

  async function handleProCheckout(): Promise<void> {
    if (isCommunityDistribution) {
      return
    }
    if (!isAuthenticated) {
      login()
      return
    }
    if (!billingConfig || !proCheckoutReady) {
      return
    }

    setCheckoutPending(true)
    setCheckoutError(null)
    try {
      await openPaddleOverlayCheckout({
        environment: billingConfig.environment,
        clientToken: billingConfig.client_token ?? '',
        priceId: billingConfig.pro_price_id ?? '',
        successUrl: billingConfig.default_success_url,
        email: user?.email,
        customData: {
          desired_tier: 'pro',
          tenant_slug: user?.tenant_slug,
          user_id: user?.id,
          user_email: user?.email,
        },
      })
    } catch (error) {
      console.error('Failed to launch Paddle checkout:', error)
      setCheckoutError(error instanceof Error ? error.message : 'Failed to launch Paddle checkout')
    } finally {
      setCheckoutPending(false)
    }
  }

  return (
    <div className="max-w-7xl mx-auto px-6 md:px-12 py-20">
      {checkoutSuccess ? (
        <div className="mb-8 rounded-sm border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700">
          Checkout completed. VigilWeave will sync the subscription to your tenant as soon as the Paddle webhook is processed.
        </div>
      ) : null}

      {/* Header */}
      <header className="mb-20 text-center max-w-3xl mx-auto">
        <span className="text-xs uppercase tracking-[0.2em] font-bold text-primary mb-4 block">
          Engineered Protection
        </span>
        <h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold tracking-tight leading-tight mb-6">
          Predictable pricing for{' '}
          <span className="text-brand-gradient">
            infrastructure defense.
          </span>
        </h1>
        <p className="text-lg text-muted-foreground leading-relaxed">
          Choose the architectural foundation that aligns with your security posture. From independent research to global portfolio management.
        </p>
      </header>

      {/* Pricing Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-0 md:gap-4 lg:gap-8 items-stretch mb-32">
        {/* Community */}
        <Card className="!rounded-sm border-l-2 border-l-transparent dark:border dark:border-white/10 hover:scale-[1.01] transition-all duration-300 shadow-[0_12px_32px_-4px_rgba(0,0,0,0.06)]">
          <Card.Header>
            <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Community</span>
            <div className="flex items-baseline gap-1">
              <span className="text-4xl font-extrabold tracking-tighter">$0</span>
              <span className="text-muted-foreground text-sm">/forever</span>
            </div>
            <Card.Description className="mt-3">
              Essential security scanners for independent developers and lean engineering teams.
            </Card.Description>
          </Card.Header>
          <Card.Content className="flex-grow">
            <ul className="space-y-4 mb-8">
              {['Self-hosted infrastructure', 'All scan engines included', 'Single triage workflow', '3 policy presets', 'SARIF export', 'Community support'].map((f) => (
                <li key={f} className="flex items-start gap-3 text-sm">
                  <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </Card.Content>
          <Card.Footer>
            <Button
              variant="secondary"
              fullWidth
              className="!rounded-sm uppercase tracking-widest text-xs font-bold py-4"
              onPress={() => window.open(DOWNLOADS_URL, '_blank')}
            >
              <Download className="mr-2 h-4 w-4" />
              Get Started
            </Button>
          </Card.Footer>
        </Card>

        {/* Pro */}
        <Card className="!rounded-sm border-l-2 border-l-primary dark:border dark:border-white/10 dark:border-l-primary relative z-10 md:scale-105 shadow-2xl">
          <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 z-10">
            <Chip variant="primary" size="sm" className="bg-primary text-primary-foreground dark:text-white dark:border dark:border-primary/50 !rounded-full text-[10px] font-bold uppercase tracking-widest px-4 shadow-sm">
              Most Popular
            </Chip>
          </div>
          <Card.Header className="pt-6">
            <span className="text-xs font-bold uppercase tracking-widest text-primary mb-2">Pro</span>
            <div className="flex items-baseline gap-1">
              <span className="text-4xl font-extrabold tracking-tighter">$69</span>
              <span className="text-muted-foreground text-sm">/dev/year</span>
            </div>
            <Card.Description className="mt-3">
              Advanced vulnerability management for scaling teams requiring high-fidelity reporting.
            </Card.Description>
          </Card.Header>
          <Card.Content className="flex-grow">
            <ul className="space-y-4 mb-8">
              {[
                { text: 'Hosted SaaS workspace', bold: true },
                { text: 'Bulk triage operations', bold: false },
                { text: 'Unlimited custom policies', bold: false },
                { text: 'Professional PDF reports', bold: false },
                { text: 'CSV / Excel export', bold: false },
                { text: '48-hour email support', bold: false },
              ].map((f) => (
                <li key={f.text} className="flex items-start gap-3 text-sm">
                  <CheckCircle2 className="h-4 w-4 text-primary mt-0.5 shrink-0 fill-primary/10" />
                  <span className={f.bold ? 'font-semibold' : ''}>{f.text}</span>
                </li>
              ))}
            </ul>
          </Card.Content>
          <Card.Footer>
            <Button
              variant="primary"
              fullWidth
              isDisabled={proButtonDisabled}
              className="!rounded-sm uppercase tracking-widest text-xs font-bold py-4"
              onPress={() => {
                void handleProCheckout()
              }}
            >
              {proButtonLabel}
            </Button>
            <p className="mt-3 text-xs text-muted-foreground">
              {isCommunityDistribution
                ? 'This build is locked to Community features. Hosted and commercial self-hosted plans are delivered through separate commercial distributions.'
                : isAuthenticated && proCheckoutReady
                  ? 'Checkout is processed by Paddle and linked to your current hosted tenant.'
                  : 'Sign in to purchase hosted Pro for your current tenant.'}
            </p>
            {!isCommunityDistribution ? (
              <p className="mt-2 text-xs text-muted-foreground">
                Need self-hosted Pro instead?{' '}
                <button
                  type="button"
                  className="font-medium text-primary underline underline-offset-4"
                  onClick={() => window.open(SALES_EMAIL_URL)}
                >
                  Contact sales
                </button>{' '}
                for commercial fulfillment.
              </p>
            ) : null}
            {isAuthenticated && billingConfigLoaded && !proCheckoutReady && !isCommunityDistribution ? (
              <p className="mt-2 text-xs text-amber-700">
                Self-serve checkout is not configured in this environment yet.
              </p>
            ) : null}
            {checkoutError ? (
              <p className="mt-2 text-xs text-danger">{checkoutError}</p>
            ) : null}
          </Card.Footer>
        </Card>

        {/* Enterprise */}
        <Card className="!rounded-sm border-l-2 border-l-transparent dark:border dark:border-white/10 hover:scale-[1.01] transition-all duration-300 shadow-[0_12px_32px_-4px_rgba(0,0,0,0.06)]">
          <Card.Header>
            <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">Enterprise</span>
            <div className="flex items-baseline gap-1">
              <span className="text-4xl font-extrabold tracking-tighter">Custom</span>
            </div>
            <Card.Description className="mt-3">
              Comprehensive governance and compliance for large-scale engineering organizations.
            </Card.Description>
          </Card.Header>
          <Card.Content className="flex-grow">
            <ul className="space-y-4 mb-8">
              {['Portfolio management', 'SSO / SAML (WorkOS)', 'Advanced RBAC controls', 'OWASP/CWE compliance', 'Dedicated MCP server', '4-hour SLA support'].map((f) => (
                <li key={f} className="flex items-start gap-3 text-sm">
                  <ShieldCheck className="h-4 w-4 text-emerald-600 mt-0.5 shrink-0" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </Card.Content>
          <Card.Footer>
            <Button
              variant="outline"
              fullWidth
              isDisabled={isCommunityDistribution}
              className="!rounded-sm uppercase tracking-widest text-xs font-bold py-4 text-primary border-primary"
              onPress={() => {
                if (!isCommunityDistribution) {
                  window.open(SALES_EMAIL_URL)
                }
              }}
            >
              <Mail className="mr-2 h-4 w-4" />
              {isCommunityDistribution ? 'Commercial Distribution Only' : 'Contact Sales'}
            </Button>
          </Card.Footer>
        </Card>
      </div>

      {/* In-Depth Comparison Table */}
      <section className="mb-32">
        <h2 className="text-2xl font-extrabold tracking-tight mb-12 text-center">In-Depth Comparison</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-muted/30 border-b-2 border-primary/10">
                <th className="py-6 px-4 text-xs font-bold uppercase tracking-widest text-muted-foreground">Capability</th>
                <th className="py-6 px-4 text-xs font-bold uppercase tracking-widest text-muted-foreground">Community</th>
                <th className="py-6 px-4 text-xs font-bold uppercase tracking-widest text-primary">Pro</th>
                <th className="py-6 px-4 text-xs font-bold uppercase tracking-widest text-muted-foreground">Enterprise</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {comparisonRows.map((row) => (
                <tr key={row.capability} className="hover:bg-muted/20 transition-colors">
                  <td className="py-5 px-4 text-sm font-semibold">{row.capability}</td>
                  <td className="py-5 px-4 text-sm text-muted-foreground">
                    {row.community}
                  </td>
                  <td className={`py-5 px-4 text-sm ${row.highlight === 'pro' ? 'font-medium text-primary' : 'text-muted-foreground'}`}>
                    {row.pro}
                  </td>
                  <td className={`py-5 px-4 text-sm ${row.highlight === 'enterprise' ? 'font-medium text-primary' : 'text-muted-foreground'}`}>
                    {row.enterprise}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Bottom CTAs — inspired by Stitch */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-20">
        {/* Dedicated Security Partner */}
        <div className="bg-card p-10 flex flex-col justify-center border-l-4 border-emerald-500 shadow-[0_12px_32px_-4px_rgba(0,0,0,0.06)]">
          <h3 className="text-2xl font-bold tracking-tight mb-4">Dedicated Security Partner?</h3>
          <p className="text-muted-foreground mb-6">
            Our Enterprise tier includes a dedicated security architect to help you map VigilWeave policies to your specific governance requirements.
          </p>
          {!isCommunityDistribution ? (
            <Button
              variant="ghost"
              className="w-fit !rounded-sm text-emerald-600 font-bold text-sm uppercase tracking-widest px-0"
              onPress={() => window.open(SALES_EMAIL_URL)}
            >
              Request Architectural Review <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          ) : null}
        </div>

        {/* Ready to scan CTA */}
        <div className="p-10 flex flex-col justify-center bg-brand-gradient text-white rounded-sm">
          <h3 className="text-2xl font-bold tracking-tight mb-4">Ready to scan?</h3>
          <p className="opacity-80 mb-6">
            Deploy VigilWeave in less than 5 minutes. Start securing your infrastructure today with our Community edition.
          </p>
          <div className="flex gap-4">
            <Button
              variant="secondary"
              className="!rounded-sm bg-white text-primary-foreground text-xs font-bold uppercase tracking-widest"
              onPress={() => window.open(DOWNLOADS_URL, '_blank')}
            >
              Quick Install
            </Button>
            <Button
              variant="outline"
              className="!rounded-sm border-white/30 text-white hover:bg-white/10 text-xs font-bold uppercase tracking-widest"
              onPress={() => navigate({ to: '/docs' })}
            >
              Documentation
            </Button>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <div className="max-w-3xl mx-auto mb-16">
        <h2 className="text-2xl font-extrabold tracking-tight text-center mb-8">Frequently Asked Questions</h2>
        <div className="space-y-6">
          <div>
            <h3 className="font-semibold text-lg mb-2">How does the free trial work?</h3>
            <p className="text-muted-foreground">
              Start on the free Community edition for self-hosted use, or contact us for a commercial evaluation of Pro and Enterprise features.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-lg mb-2">Can I self-host the Pro/Enterprise tiers?</h3>
            <p className="text-muted-foreground">
              Yes. Paid self-hosted deployments are delivered as commercial artifacts with license-based entitlements, while SaaS runs as a hosted commercial service.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-lg mb-2">What counts as a developer?</h3>
            <p className="text-muted-foreground">
              For paid plans, a seat typically maps to one active user in the product. The billing owner seat can be handled separately under commercial terms.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-lg mb-2">Is there a limit on scans?</h3>
            <p className="text-muted-foreground">
              Community is intended for self-hosted internal use. Commercial plans add hosted workflows, reporting, and support; exact usage terms depend on the purchased plan.
            </p>
          </div>
        </div>
      </div>

      {/* Contact CTA */}
      <div className="text-center">
        <p className="text-muted-foreground mb-4">Still have questions?</p>
        <Button
          variant="outline"
          className="!rounded-sm"
          onPress={() => window.open(SUPPORT_EMAIL_URL)}
        >
          Contact Support
        </Button>
      </div>
    </div>
  )
}
