import type { JSX } from 'react'

import { LegalPageShell } from './legal/LegalPageShell'

export function RefundPolicyPage(): JSX.Element {
  return (
    <LegalPageShell
      title="Refund Policy"
      summary="This policy describes how VigilWeave handles refunds for hosted SaaS purchases and related commercial transactions."
      effectiveDate="2026-04-05"
    >
      <h2>1. Subscription Charges</h2>
      <p>
        Hosted SaaS subscriptions are billed according to the plan and billing interval selected at purchase or set out
        in a commercial order form.
      </p>

      <h2>2. Standard Refunds</h2>
      <p>
        Unless a separate enterprise agreement states otherwise, customers may request a refund within 14 days of an
        initial SaaS purchase if the service has not materially met the described onboarding and access expectations.
      </p>

      <h2>3. Renewals</h2>
      <p>
        Renewal charges are generally non-refundable once a renewal period has started, unless required by law or
        agreed in writing.
      </p>

      <h2>4. Enterprise Agreements</h2>
      <p>
        Enterprise purchases, annual commitments, professional services, and custom commercial terms may be governed by
        separate contract provisions that override this standard policy.
      </p>

      <h2>5. Requesting a Refund</h2>
      <p>
        Example billing contact: billing@example.com (a placeholder, not a monitored inbox).
        A refund request would include the purchasing email, organization name, and the
        reason for the request.
      </p>
    </LegalPageShell>
  )
}
