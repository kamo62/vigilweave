import type { JSX } from 'react'

import { LegalPageShell } from './legal/LegalPageShell'

export function TermsPage(): JSX.Element {
  return (
    <LegalPageShell
      title="Terms and Conditions"
      summary="These terms govern access to the VigilWeave hosted service, public website, APIs, and related commercial offerings."
      effectiveDate="2026-04-05"
    >
      <h2>1. Agreement</h2>
      <p>
        By accessing VigilWeave, you agree to these terms on behalf of yourself or the organization you represent.
        If you do not agree, do not use the service.
      </p>

      <h2>2. Service Scope</h2>
      <p>
        VigilWeave is a SaaS application security and code quality platform. Access may include hosted dashboards,
        repository onboarding, scans, reporting, APIs, and related operator tooling.
      </p>

      <h2>3. Accounts and Organizations</h2>
      <p>
        SaaS access is organization-based. Each customer organization is treated as a separate tenant. Tenant admins
        are responsible for user access, repository connections, and use of the service inside their organization.
      </p>

      <h2>4. Acceptable Use</h2>
      <p>
        You may not use VigilWeave to violate law, scan repositories you are not authorized to access, interfere with
        the service, or attempt to bypass licensing, security, or tenant-isolation controls.
      </p>

      <h2>5. Commercial Terms</h2>
      <p>
        Paid subscriptions, evaluations, or enterprise agreements may include additional order forms or commercial
        terms. If there is a conflict, the signed commercial agreement controls for the purchased service.
      </p>

      <h2>6. Availability and Changes</h2>
      <p>
        We may update features, limits, pricing, or operational policies over time. We may suspend access where needed
        for security, abuse prevention, billing issues, or legal compliance.
      </p>

      <h2>7. Intellectual Property</h2>
      <p>
        VigilWeave and its hosted service, branding, and platform materials remain our property except for customer
        content, repositories, and customer-owned configuration data.
      </p>

      <h2>8. Contact</h2>
      <p>
        Questions about these terms may be sent to support@vigilweave.com.
      </p>
    </LegalPageShell>
  )
}
