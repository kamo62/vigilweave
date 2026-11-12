import { useEffect, useState } from 'react'
import { Button, Card } from '@heroui/react'

import {
  createBillingPortalSession,
  fetchCurrentTenantRecord,
  fetchCurrentTenantSubscription,
  fetchSelfHostedLicense,
  type BillingSubscriptionRecord,
  type SelfHostedLicenseRecord,
  type TenantRecord,
} from '@/lib/api'
import { useLicense } from '@/lib/hooks/useLicense'
import { useAuth } from '@/lib/useAuth'

export function BillingTab() {
  const { user } = useAuth()
  const { isCommunityDistribution } = useLicense()
  const [tenant, setTenant] = useState<TenantRecord | null>(null)
  const [subscription, setSubscription] = useState<BillingSubscriptionRecord | null>(null)
  const [license, setLicense] = useState<SelfHostedLicenseRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [portalPending, setPortalPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (isCommunityDistribution) {
      setTenant(null)
      setSubscription(null)
      setLicense(null)
      setError(null)
      setLoading(false)
      return
    }

    let cancelled = false

    void (async () => {
      try {
        setLoading(true)
        const [tenantRecord, subscriptionRecord] = await Promise.all([
          fetchCurrentTenantRecord(),
          fetchCurrentTenantSubscription(),
        ])
        if (cancelled) {
          return
        }
        setTenant(tenantRecord)
        setSubscription(subscriptionRecord)

        if (tenantRecord?.deployment_mode === 'self_hosted' && user?.role === 'admin') {
          try {
            const licenseRecord = await fetchSelfHostedLicense()
            if (!cancelled) {
              setLicense(licenseRecord)
            }
          } catch (licenseError) {
            if (!cancelled) {
              setError(
                licenseError instanceof Error ? licenseError.message : 'Failed to load self-hosted license',
              )
            }
          }
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Failed to load billing state')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [isCommunityDistribution, user?.role])

  if (isCommunityDistribution) {
    return (
      <Card className="rounded-sm border border-border/60">
        <Card.Header>
          <div>
            <h3 className="text-lg font-semibold">Billing</h3>
            <p className="text-sm text-muted-foreground">
              The Community distribution does not support in-app billing, license activation, or commercial fulfillment.
            </p>
          </div>
        </Card.Header>
      </Card>
    )
  }

  async function openPortal(): Promise<void> {
    try {
      setPortalPending(true)
      setError(null)
      const session = await createBillingPortalSession()
      if (!session.overview_url) {
        throw new Error('Paddle did not return a portal overview URL')
      }
      window.location.assign(session.overview_url)
    } catch (portalError) {
      setError(portalError instanceof Error ? portalError.message : 'Failed to open billing portal')
    } finally {
      setPortalPending(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card className="rounded-sm border border-border/60">
        <Card.Header>
          <div>
            <h3 className="text-lg font-semibold">Tenant Billing</h3>
            <p className="text-sm text-muted-foreground">
              Review the current commercial state for this tenant and jump into Paddle-hosted management flows.
            </p>
          </div>
        </Card.Header>
        <Card.Content className="space-y-4 text-sm">
          {loading ? <p className="text-muted-foreground">Loading billing state…</p> : null}
          {!loading && tenant ? (
            <>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-[0.08em] text-muted-foreground">Tenant</p>
                  <p className="font-medium">{tenant.display_name}</p>
                  <p className="text-muted-foreground">{tenant.slug}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.08em] text-muted-foreground">Plan</p>
                  <p className="font-medium capitalize">{tenant.plan_tier}</p>
                  <p className="text-muted-foreground capitalize">{tenant.billing_status.replace('_', ' ')}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.08em] text-muted-foreground">Deployment</p>
                  <p className="font-medium capitalize">{tenant.deployment_mode.replace('_', ' ')}</p>
                  <p className="text-muted-foreground">{tenant.billing_email ?? 'No billing email recorded yet'}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.08em] text-muted-foreground">Subscription</p>
                  <p className="font-medium">{subscription?.provider_subscription_id ?? 'No synced subscription yet'}</p>
                  <p className="text-muted-foreground">{subscription?.status ?? 'Waiting for Paddle sync'}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                <Button
                  variant="primary"
                  className="rounded-sm"
                  isDisabled={portalPending || !tenant.paddle_customer_id}
                  onPress={() => {
                    void openPortal()
                  }}
                >
                  {portalPending ? 'Opening Portal…' : 'Open Billing Portal'}
                </Button>
              </div>
            </>
          ) : null}

          {!loading && !tenant ? (
            <p className="text-muted-foreground">No tenant billing record exists yet for this environment.</p>
          ) : null}

          {error ? <p className="text-danger">{error}</p> : null}
        </Card.Content>
      </Card>

      {tenant?.deployment_mode === 'self_hosted' && user?.role === 'admin' ? (
        <Card className="rounded-sm border border-border/60">
          <Card.Header>
            <div>
              <h3 className="text-lg font-semibold">Self-Hosted License</h3>
              <p className="text-sm text-muted-foreground">
                This key is issued from the VigilWeave license server after paid fulfillment is confirmed.
              </p>
            </div>
          </Card.Header>
          <Card.Content className="space-y-3 text-sm">
            <p><span className="font-medium">License ID:</span> {license?.license_id ?? 'Not issued yet'}</p>
            <p><span className="font-medium">Key Prefix:</span> {license?.key_prefix ?? 'Not issued yet'}</p>
            <p><span className="font-medium">Status:</span> {license?.status ?? 'Pending'}</p>
            {license?.license_key ? (
              <div>
                <p className="mb-2 font-medium">Issued License Key</p>
                <textarea
                  readOnly
                  className="min-h-24 w-full rounded-sm border border-border bg-muted/30 px-3 py-2 font-mono text-xs"
                  value={license.license_key}
                />
              </div>
            ) : (
              <p className="text-muted-foreground">The license key will appear here after fulfillment runs successfully.</p>
            )}
          </Card.Content>
        </Card>
      ) : null}
    </div>
  )
}
