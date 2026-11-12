import type { JSX } from 'react'

import { LegalPageShell } from './legal/LegalPageShell'

export function PrivacyPage(): JSX.Element {
  return (
    <LegalPageShell
      title="Privacy Policy"
      summary="This policy explains what information VigilWeave processes for the hosted SaaS and public website, and how that information is used."
      effectiveDate="2026-04-05"
    >
      <h2>1. Information We Process</h2>
      <p>
        We may process account information, organization metadata, authentication details, billing and commercial
        contact details, repository connection metadata, scan results, and operational logs needed to run the service.
      </p>

      <h2>2. How We Use Information</h2>
      <p>
        We use data to authenticate users, isolate tenants, perform scans, display findings, operate support workflows,
        prevent abuse, and improve reliability and security of the platform.
      </p>

      <h2>3. Repository and Scan Data</h2>
      <p>
        Repository access is used only to perform the scans and workflows requested by your organization. Scan outputs,
        findings, and project metadata are stored as part of the hosted service for your tenant.
      </p>

      <h2>4. Sharing</h2>
      <p>
        We do not sell customer data. We may share data with subprocessors that help us provide hosting,
        authentication, infrastructure, customer support, and billing services.
      </p>

      <h2>5. Retention</h2>
      <p>
        We retain account, audit, and scan data as needed to provide the service, satisfy contractual commitments, and
        support security and compliance obligations.
      </p>

      <h2>6. Security</h2>
      <p>
        We use administrative, technical, and organizational controls designed to protect customer data and maintain
        tenant isolation in the hosted environment.
      </p>

      <h2>7. Contact</h2>
      <p>
        Privacy questions or requests may be sent to privacy@vigilweave.com.
      </p>
    </LegalPageShell>
  )
}
