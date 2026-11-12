export function Scanning() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">Scanning</h2>
        <p className="text-muted-foreground">
          VigilWeave provides comprehensive application security scanning across
          your entire codebase. Multiple scanning engines run in isolated
          containers and produce unified, normalized findings — all managed from
          a single dashboard.
        </p>
      </div>

      {/* Scanning Capabilities */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Scanning Capabilities</h3>
        <p className="text-muted-foreground">
          Every scan automatically runs the full suite of security engines
          appropriate for your project. VigilWeave detects language, framework,
          and infrastructure patterns to apply the right analysis — no
          configuration required.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border rounded-sm overflow-hidden">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-2 font-semibold text-foreground">Capability</th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">What It Detects</th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">Coverage</th>
              </tr>
            </thead>
            <tbody className="text-muted-foreground divide-y divide-border">
              <tr><td className="px-4 py-2 font-medium text-foreground">Static Analysis (SAST)</td><td className="px-4 py-2">Injection flaws, insecure patterns, unsafe API usage, code quality issues</td><td className="px-4 py-2">Python, JavaScript, TypeScript, Java, Go, Ruby, C#, Kotlin, Swift, Rust, and 20+ more</td></tr>
              <tr><td className="px-4 py-2 font-medium text-foreground">Secrets Detection</td><td className="px-4 py-2">API keys, passwords, tokens, private keys, connection strings</td><td className="px-4 py-2">All file types — scans working tree and full git history</td></tr>
              <tr><td className="px-4 py-2 font-medium text-foreground">Dependency Analysis</td><td className="px-4 py-2">Known CVEs in third-party packages, outdated dependencies, license risks</td><td className="px-4 py-2">npm, pip, Maven, Go modules, Cargo, NuGet, OS packages</td></tr>
              <tr><td className="px-4 py-2 font-medium text-foreground">Software Composition Analysis (SCA)</td><td className="px-4 py-2">Vulnerable dependencies, license risks, outdated packages, transitive dependency issues</td><td className="px-4 py-2">npm, pip, Maven, Go modules, Cargo, NuGet, Bundler, Composer</td></tr>
              <tr><td className="px-4 py-2 font-medium text-foreground">Infrastructure as Code</td><td className="px-4 py-2">Misconfigured cloud resources, insecure defaults, compliance violations</td><td className="px-4 py-2">Terraform, CloudFormation, Kubernetes, Helm, Dockerfiles</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Scan Types */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Scan Types</h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-sm border border-border p-4 space-y-1">
            <h4 className="font-semibold text-foreground">SAST (Static Analysis)</h4>
            <p className="text-sm text-muted-foreground">
              Multiple analysis engines scan your source code for vulnerabilities,
              insecure patterns, and code quality issues without executing the
              application. Covers 25+ languages with language-specific rule sets.
            </p>
          </div>
          <div className="rounded-sm border border-border p-4 space-y-1">
            <h4 className="font-semibold text-foreground">Secrets Detection</h4>
            <p className="text-sm text-muted-foreground">
              Deep scans across the full git history and working tree to find
              leaked API keys, passwords, tokens, and private keys — including
              secrets that were committed and later removed.
            </p>
          </div>
          <div className="rounded-sm border border-border p-4 space-y-1">
            <h4 className="font-semibold text-foreground">Infrastructure as Code</h4>
            <p className="text-sm text-muted-foreground">
              Validates Terraform, CloudFormation, Kubernetes manifests, and
              Dockerfiles against hundreds of security best practices and
              compliance benchmarks (CIS, SOC 2, PCI-DSS).
            </p>
          </div>
          <div className="rounded-sm border border-border p-4 space-y-1">
            <h4 className="font-semibold text-foreground">Software Composition Analysis (SCA)</h4>
            <p className="text-sm text-muted-foreground">
              Enumerates all third-party dependencies from lock files and
              manifests, checks them against multiple vulnerability databases
              (NVD, GitHub Advisories, OSV), and flags license risks and
              transitive dependency issues.
            </p>
          </div>
        </div>
      </section>

      {/* Finding Triage Workflow */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Finding Triage Workflow</h3>
        <p className="text-muted-foreground">
          Every finding produced by a scan enters a triage pipeline. Use the
          dashboard to review, classify, and resolve findings efficiently.
        </p>
        <ol className="list-decimal list-inside space-y-2 text-muted-foreground">
          <li>
            <strong>Open</strong> &mdash; New finding, not yet reviewed. Appears in
            the active findings list.
          </li>
          <li>
            <strong>Confirmed</strong> &mdash; A team member has verified the finding
            is a real issue and it needs remediation.
          </li>
          <li>
            <strong>False Positive</strong> &mdash; The finding is not a real
            vulnerability. Mark it as false positive to suppress it in future scans.
          </li>
          <li>
            <strong>Waived</strong> &mdash; The finding is acknowledged but accepted
            via a policy waiver with an expiration date and justification.
          </li>
          <li>
            <strong>Fixed</strong> &mdash; The underlying code has been remediated.
            VigilWeave automatically closes findings that no longer appear in
            subsequent scans.
          </li>
        </ol>
      </section>

      {/* Bulk Triage */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Bulk Triage</h3>
        <div className="rounded-sm border border-primary/20 bg-primary/5 p-4 space-y-1">
          <p className="text-sm font-semibold text-primary">
            Pro Feature
          </p>
          <p className="text-sm text-muted-foreground">
            Bulk triage is available on the <strong>Pro</strong> and{" "}
            <strong>Enterprise</strong> tiers. Community users triage findings
            one at a time.
          </p>
        </div>
        <p className="text-muted-foreground">
          When reviewing large scans, you can select multiple findings and apply
          a triage status in a single action &mdash; dramatically reducing review
          time for recurring patterns or known false positives.
        </p>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            How It Works
          </h4>
          <ol className="list-decimal list-inside space-y-2 text-muted-foreground">
            <li>
              <strong>Open a scan</strong> &mdash; Navigate to a completed scan
              from the Dashboard or Scans list.
            </li>
            <li>
              <strong>Select findings</strong> &mdash; Click the checkbox next to
              individual findings, use the &ldquo;Select all on page&rdquo;
              toggle, or &ldquo;Select all matching filters&rdquo; to select
              across pages.
            </li>
            <li>
              <strong>Filter first, then select</strong> &mdash; Apply severity,
              status, or tool filters to narrow down findings before selecting.
              This is the most efficient approach for triaging categories like
              &ldquo;all Info findings from engine X.&rdquo;
            </li>
            <li>
              <strong>Apply status</strong> &mdash; A bulk action toolbar appears
              showing the count of selected findings. Click one of the status
              buttons to apply:
            </li>
          </ol>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-border rounded-sm overflow-hidden">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">Status</th>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">Use When</th>
                </tr>
              </thead>
              <tbody className="text-muted-foreground divide-y divide-border">
                <tr>
                  <td className="px-4 py-2 font-medium text-foreground">Confirmed</td>
                  <td className="px-4 py-2">Verified as real issues — mark a batch to track remediation</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-medium text-foreground">False Positive</td>
                  <td className="px-4 py-2">Not real vulnerabilities — dismiss a category of false alerts</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-medium text-foreground">Won&apos;t Fix</td>
                  <td className="px-4 py-2">Acknowledged but accepted as-is — e.g. test code, demo projects</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-medium text-foreground">Open</td>
                  <td className="px-4 py-2">Reset back to unreviewed — undo a previous triage decision</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            API
          </h4>
          <p className="text-sm text-muted-foreground">
            Bulk triage is also available via the REST API for scripted workflows:
          </p>
          <div className="code-block">
            <pre>{`# Bulk triage findings
curl -X POST https://app.vigilweave.com/api/v1/scans/42/findings/bulk-triage \\
  -H "Authorization: Bearer vw_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "finding_ids": [101, 102, 103, 104],
    "review_status": "false_positive",
    "comment": "Test fixtures, not production code"
  }'`}</pre>
          </div>
        </div>
      </section>

      {/* SARIF Export */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">SARIF Export</h3>
        <p className="text-muted-foreground">
          VigilWeave supports exporting scan results in{" "}
          <strong>SARIF v2.1.0</strong> (Static Analysis Results Interchange
          Format), which is compatible with GitHub Code Scanning, Azure DevOps, and
          other tools.
        </p>
        <div className="code-block">
          <pre>{`# Export scan results as SARIF
curl -X GET http://localhost:8000/api/v1/scans/{scan_id}/sarif \\
  -H "Authorization: Bearer vw_your_api_key" \\
  -o results.sarif.json

# Upload to GitHub Code Scanning
gh api repos/{owner}/{repo}/code-scanning/sarifs \\
  --method POST \\
  -f "commit_sha=$(git rev-parse HEAD)" \\
  -f "ref=refs/heads/main" \\
  -f "sarif=@results.sarif.json"`}</pre>
        </div>
        <p className="text-sm text-muted-foreground">
          SARIF export includes tool metadata, rule descriptions, source locations,
          and severity mappings.
        </p>
      </section>
    </div>
  );
}
