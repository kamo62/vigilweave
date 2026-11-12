export function PolicyGovernance() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">Policy &amp; Governance</h2>
        <p className="text-muted-foreground">
          Quality gates let you enforce security standards automatically. Define
          thresholds for finding severity, set up approval workflows, and maintain a
          full audit trail of every policy decision.
        </p>
      </div>

      {/* Quality Gates */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Quality Gates</h3>
        <p className="text-muted-foreground">
          A quality gate is a set of rules that a scan must pass before a deployment
          or merge is allowed to proceed. Gates are evaluated automatically after
          every scan completes. If a gate fails, VigilWeave can block the CI
          pipeline or post a PR comment.
        </p>
        <p className="text-muted-foreground">
          Each gate defines thresholds per severity level. For example, a gate might
          allow up to 5 medium-severity findings but zero critical findings.
        </p>
      </section>

      {/* Built-in Presets */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Built-in Presets</h3>
        <p className="text-muted-foreground">
          VigilWeave ships with three policy presets to help you get started quickly.
          You can use them as-is or clone and customize them.
        </p>

        <div className="space-y-4">
          <div className="rounded-sm border border-border p-4 space-y-2">
            <h4 className="font-semibold text-foreground">Lenient</h4>
            <p className="text-sm text-muted-foreground">
              Designed for early-stage projects or internal tools where flexibility
              matters more than strict enforcement.
            </p>
            <div className="code-block">
              <pre>{`{
  "name": "Lenient",
  "max_critical": 3,
  "max_high": 10,
  "max_medium": -1,    // unlimited
  "max_low": -1,       // unlimited
  "block_on_secrets": true,
  "require_approval": false
}`}</pre>
            </div>
          </div>

          <div className="rounded-sm border border-border p-4 space-y-2">
            <h4 className="font-semibold text-foreground">Balanced</h4>
            <p className="text-sm text-muted-foreground">
              A good default for most teams. Blocks critical issues while allowing
              some flexibility on lower-severity findings.
            </p>
            <div className="code-block">
              <pre>{`{
  "name": "Balanced",
  "max_critical": 0,
  "max_high": 5,
  "max_medium": 20,
  "max_low": -1,       // unlimited
  "block_on_secrets": true,
  "require_approval": false
}`}</pre>
            </div>
          </div>

          <div className="rounded-sm border border-border p-4 space-y-2">
            <h4 className="font-semibold text-foreground">Strict</h4>
            <p className="text-sm text-muted-foreground">
              Maximum security posture for production-facing or compliance-sensitive
              applications. Zero tolerance for critical and high findings.
            </p>
            <div className="code-block">
              <pre>{`{
  "name": "Strict",
  "max_critical": 0,
  "max_high": 0,
  "max_medium": 5,
  "max_low": 20,
  "block_on_secrets": true,
  "require_approval": true
}`}</pre>
            </div>
          </div>
        </div>
      </section>

      {/* Custom Policies */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Custom Policy Creation</h3>
        <p className="text-muted-foreground">
          Create custom policies from the Policies page or via the API. Custom
          policies support all the same fields as presets, plus additional options:
        </p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground">
          <li>
            <strong>Tool-specific thresholds</strong> &mdash; Set different limits
            per scan engine (e.g., zero secrets findings, up to 3 SAST highs).
          </li>
          <li>
            <strong>Category filters</strong> &mdash; Apply rules only to specific
            finding categories like SQL injection or XSS.
          </li>
          <li>
            <strong>Branch patterns</strong> &mdash; Enforce strict policies only on{" "}
            <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">
              main
            </code>{" "}
            and{" "}
            <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">
              release/*
            </code>{" "}
            while keeping development branches lenient.
          </li>
          <li>
            <strong>Tenant defaults</strong> &mdash; Mark a policy as the default
            baseline for new projects in the tenant.
          </li>
        </ul>
        <div className="code-block">
          <pre>{`curl -X POST http://localhost:8000/api/v1/policies \\
  -H "Authorization: Bearer YOUR_API_KEY_HERE" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "Production Gate",
    "max_critical": 0,
    "max_high": 0,
    "max_medium": 3,
    "max_low": -1,
    "block_on_secrets": true,
    "require_approval": true,
    "branch_patterns": ["main", "release/*"]
  }'`}</pre>
        </div>
      </section>

      {/* Waivers */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Waivers</h3>
        <p className="text-muted-foreground">
          Sometimes a finding is a known acceptable risk. Waivers let you
          temporarily or permanently suppress specific findings while maintaining a
          full record of the decision.
        </p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground">
          <li>Each waiver requires a <strong>justification</strong> explaining why the risk is accepted.</li>
          <li>Waivers can have an <strong>expiration date</strong> after which the finding resurfaces.</li>
          <li>Only tenant admins can approve waivers.</li>
          <li>All waiver actions are recorded in the audit log with timestamps and user attribution.</li>
        </ul>
      </section>

      {/* Audit Trail */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Audit Trail</h3>
        <p className="text-muted-foreground">
          VigilWeave maintains an immutable audit log of every governance action.
          This is essential for compliance frameworks like SOC 2, ISO 27001, and
          PCI-DSS. The audit trail captures:
        </p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground">
          <li>Policy creation, modification, and deletion events</li>
          <li>Gate pass/fail results for every scan</li>
          <li>Finding triage decisions (confirmed, false positive, waived)</li>
          <li>Waiver approvals and expirations</li>
          <li>User and timestamp for every action</li>
        </ul>
      </section>
    </div>
  );
}
