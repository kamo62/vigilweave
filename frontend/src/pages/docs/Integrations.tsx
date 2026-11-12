export function Integrations() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">Integrations</h2>
        <p className="text-muted-foreground">
          VigilWeave integrates with your existing development workflow. Run scans
          in CI/CD pipelines, get findings in your IDE, and sync data with
          third-party security platforms.
        </p>
      </div>

      {/* GitHub Actions */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">GitHub Actions</h3>
        <p className="text-muted-foreground">
          Add VigilWeave to your GitHub Actions workflow to scan every pull request
          automatically. The action posts findings as PR annotations and can block
          merges based on your quality gate policy.
        </p>
        <div className="code-block">
          <pre>{`# .github/workflows/vigilweave.yml
name: VigilWeave Security Scan
on:
  pull_request:
    branches: [main]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run VigilWeave Scan
        uses: vigilweave/action@v1
        with:
          vigilweave_url: https://your-instance.example.com
          api_key: \${{ secrets.VIGILWEAVE_API_KEY }}
          scan_type: comprehensive    # comprehensive | fast | security-only
          fail_on_critical: true      # Fail if critical findings detected
          fail_on_high: false         # Optional: also fail on high findings`}</pre>
        </div>
        <p className="text-sm text-muted-foreground">
          The action uploads results as SARIF to GitHub Code Scanning, so findings
          also appear in the Security tab of your repository.
        </p>
      </section>

      {/* Azure DevOps */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Azure DevOps</h3>
        <p className="text-muted-foreground">
          Use the VigilWeave Azure DevOps task to integrate security scanning into
          your Azure Pipelines.
        </p>
        <div className="code-block">
          <pre>{`# azure-pipelines.yml
steps:
  - task: VigilWeaveScan@1
    inputs:
      vigilweaveUrl: https://your-instance.example.com
      apiKey: $(VIGILWEAVE_API_KEY)
      scanType: comprehensive
      failOnCritical: true

  # Publish SARIF to Azure DevOps Advanced Security
  - task: AdvancedSecurity-Publish@1
    inputs:
      SarifFilePattern: $(Build.ArtifactStagingDirectory)/vigilweave/*.sarif`}</pre>
        </div>
      </section>

      {/* VS Code Extension */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">VS Code Extension</h3>
        <p className="text-muted-foreground">
          The VigilWeave VS Code extension brings findings directly into your
          editor. Install it from the VS Code Marketplace:
        </p>
        <div className="code-block">
          <pre>{`# Install via CLI
code --install-extension vigilweave.vigilweave-vscode`}</pre>
        </div>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground">
          <li>Inline annotations on lines with active findings</li>
          <li>Problems panel integration with severity icons</li>
          <li>Quick-fix suggestions for common vulnerability patterns</li>
          <li>One-click triage: mark findings as false positive or waived directly from the editor</li>
          <li>Trigger on-demand scans of the current file or workspace</li>
        </ul>
      </section>

      {/* MCP Integration */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">MCP Integration for Claude Desktop</h3>
        <p className="text-muted-foreground">
          VigilWeave exposes a Model Context Protocol (MCP) server that allows AI
          assistants like Claude Desktop to query your security data conversationally.
        </p>
        <div className="code-block">
          <pre>{`// claude_desktop_config.json
{
  "mcpServers": {
    "vigilweave": {
      "command": "npx",
      "args": ["-y", "@vigilweave/mcp-server"],
      "env": {
        "VIGILWEAVE_API_KEY": "vw_your_api_key",
        "VIGILWEAVE_API_URL": "http://localhost:8000"
      }
    }
  }
}`}</pre>
        </div>
        <p className="text-sm text-muted-foreground">
          Once configured, you can ask Claude questions like &ldquo;What are the
          open critical findings in the payments project?&rdquo; or &ldquo;Show me
          the MTTR trend for the last 30 days.&rdquo;
        </p>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            Available Tools & Permissions
          </h4>
          <p className="text-sm text-muted-foreground">
            The MCP server exposes 10 tools. Authentication uses the same API key
            system as the REST API &mdash; the key&apos;s scopes determine what
            operations are permitted. There is no separate MCP permission model.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-border rounded-sm overflow-hidden">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">Tool</th>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">Type</th>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">Description</th>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">Required Scope</th>
                </tr>
              </thead>
              <tbody className="text-muted-foreground divide-y divide-border">
                <tr>
                  <td className="px-4 py-2 font-mono text-xs text-foreground">list_projects</td>
                  <td className="px-4 py-2"><span className="inline-block rounded-sm bg-emerald-500/10 px-1.5 py-0.5 text-xs font-medium text-emerald-500">Read</span></td>
                  <td className="px-4 py-2">List all projects in the tenant</td>
                  <td className="px-4 py-2 font-mono text-xs">project:read</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs text-foreground">search_scans</td>
                  <td className="px-4 py-2"><span className="inline-block rounded-sm bg-emerald-500/10 px-1.5 py-0.5 text-xs font-medium text-emerald-500">Read</span></td>
                  <td className="px-4 py-2">Search scan history, filter by repo</td>
                  <td className="px-4 py-2 font-mono text-xs">scan:read</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs text-foreground">get_scan_detail</td>
                  <td className="px-4 py-2"><span className="inline-block rounded-sm bg-emerald-500/10 px-1.5 py-0.5 text-xs font-medium text-emerald-500">Read</span></td>
                  <td className="px-4 py-2">Full scan details with quality metrics</td>
                  <td className="px-4 py-2 font-mono text-xs">scan:read</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs text-foreground">get_quality_gate_status</td>
                  <td className="px-4 py-2"><span className="inline-block rounded-sm bg-emerald-500/10 px-1.5 py-0.5 text-xs font-medium text-emerald-500">Read</span></td>
                  <td className="px-4 py-2">Quality gate pass/fail with scores</td>
                  <td className="px-4 py-2 font-mono text-xs">scan:read</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs text-foreground">search_findings</td>
                  <td className="px-4 py-2"><span className="inline-block rounded-sm bg-emerald-500/10 px-1.5 py-0.5 text-xs font-medium text-emerald-500">Read</span></td>
                  <td className="px-4 py-2">List findings, filter by severity</td>
                  <td className="px-4 py-2 font-mono text-xs">scan:read</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs text-foreground">get_project_health</td>
                  <td className="px-4 py-2"><span className="inline-block rounded-sm bg-emerald-500/10 px-1.5 py-0.5 text-xs font-medium text-emerald-500">Read</span></td>
                  <td className="px-4 py-2">Aggregate health across all repos</td>
                  <td className="px-4 py-2 font-mono text-xs">project:read</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs text-foreground">get_capabilities</td>
                  <td className="px-4 py-2"><span className="inline-block rounded-sm bg-emerald-500/10 px-1.5 py-0.5 text-xs font-medium text-emerald-500">Read</span></td>
                  <td className="px-4 py-2">System capabilities, license tier, features</td>
                  <td className="px-4 py-2 font-mono text-xs">scan:read</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs text-foreground">get_policy_status</td>
                  <td className="px-4 py-2"><span className="inline-block rounded-sm bg-emerald-500/10 px-1.5 py-0.5 text-xs font-medium text-emerald-500">Read</span></td>
                  <td className="px-4 py-2">List configured policy profiles</td>
                  <td className="px-4 py-2 font-mono text-xs">scan:read</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs text-foreground">create_scan</td>
                  <td className="px-4 py-2"><span className="inline-block rounded-sm bg-amber-500/10 px-1.5 py-0.5 text-xs font-medium text-amber-500">Write</span></td>
                  <td className="px-4 py-2">Trigger a new scan for a repository</td>
                  <td className="px-4 py-2 font-mono text-xs">scan:write</td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs text-foreground">triage_finding</td>
                  <td className="px-4 py-2"><span className="inline-block rounded-sm bg-amber-500/10 px-1.5 py-0.5 text-xs font-medium text-amber-500">Write</span></td>
                  <td className="px-4 py-2">Update review status of a finding</td>
                  <td className="px-4 py-2 font-mono text-xs">scan:write</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-sm border border-yellow-500/30 bg-yellow-500/5 p-4 space-y-1">
          <p className="text-sm font-semibold text-yellow-500">
            Permission Model
          </p>
          <p className="text-sm text-muted-foreground">
            MCP tools inherit permissions from the API key used in{" "}
            <code className="bg-muted px-1 rounded font-mono text-xs">
              VIGILWEAVE_API_KEY
            </code>
            . A key with{" "}
            <code className="bg-muted px-1 rounded font-mono text-xs">
              scan:read, project:read
            </code>{" "}
            scopes will only be able to use the 8 read-only tools. To enable{" "}
            <code className="bg-muted px-1 rounded font-mono text-xs">
              create_scan
            </code>{" "}
            and{" "}
            <code className="bg-muted px-1 rounded font-mono text-xs">
              triage_finding
            </code>
            , the key must also include{" "}
            <code className="bg-muted px-1 rounded font-mono text-xs">
              scan:write
            </code>
            . Admin-scoped keys grant access to all tools.
          </p>
        </div>
      </section>

      {/* Prisma Cloud */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Prisma Cloud Sync</h3>
        <p className="text-muted-foreground">
          Sync VigilWeave findings with Palo Alto Prisma Cloud for a unified view
          across code security, cloud security posture, and runtime protection.
        </p>
        <div className="code-block">
          <pre>{`# Configure Prisma Cloud integration
curl -X POST http://localhost:8000/api/v1/integrations \\
  -H "Authorization: Bearer vw_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "type": "prisma_cloud",
    "config": {
      "api_url": "https://api.prismacloud.io",
      "access_key": "your-prisma-access-key",
      "secret_key": "your-prisma-secret-key",
      "sync_interval_minutes": 30
    }
  }'`}</pre>
        </div>
      </section>

      {/* SonarQube */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">SonarQube Rule Import</h3>
        <p className="text-muted-foreground">
          Import your existing SonarQube quality profiles and rules into VigilWeave
          to maintain consistency across platforms. VigilWeave maps SonarQube rules to
          equivalent built-in analysis rules where possible.
        </p>
        <div className="code-block">
          <pre>{`# Import SonarQube rules
curl -X POST http://localhost:8000/api/v1/integrations/sonarqube/import \\
  -H "Authorization: Bearer vw_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "sonarqube_url": "https://sonar.example.com",
    "token": "squ_your_sonarqube_token",
    "quality_profile": "your-profile-name",
    "language": "python"
  }'`}</pre>
        </div>
        <p className="text-sm text-muted-foreground">
          After import, VigilWeave shows a mapping report indicating which rules
          were matched, which have no equivalent, and any conflicts.
        </p>
      </section>
    </div>
  );
}
