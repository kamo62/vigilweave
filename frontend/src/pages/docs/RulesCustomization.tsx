export function RulesCustomization() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">
          Rules &amp; Customization
        </h2>
        <p className="text-muted-foreground">
          VigilWeave ships with hundreds of built-in rules across every managed
          analyzer. You can extend coverage by importing SonarQube / SonarCloud
          quality profiles, configuring analyzer rule sets, or uploading custom
          rule packs.
        </p>
      </div>

      {/* SonarQube / SonarCloud Import */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Importing SonarQube / SonarCloud Rules
        </h3>
        <p className="text-muted-foreground">
          If your team already uses SonarQube or SonarCloud, you can import your
          existing quality profiles into VigilWeave. VigilWeave maps SonarQube
          rules to equivalent built-in analysis rules and generates a mapping
          report showing matched, unmatched, and conflicting rules.
        </p>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            From the UI (Enterprise)
          </h4>
          <ol className="list-decimal list-inside space-y-1 text-sm text-muted-foreground">
            <li>
              Navigate to{" "}
              <strong>Integrations → SonarQube Rule Import</strong>.
            </li>
            <li>
              Enter your SonarQube server URL (or{" "}
              <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">
                https://sonarcloud.io
              </code>{" "}
              for SonarCloud).
            </li>
            <li>Paste your SonarQube / SonarCloud API token.</li>
            <li>
              Select the <strong>quality profile</strong> and{" "}
              <strong>language</strong> to import.
            </li>
            <li>
              Click <strong>Import</strong>. VigilWeave fetches the rules and
              creates a rule pack automatically.
            </li>
          </ol>
        </div>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            Via the API (automation)
          </h4>
          <div className="code-block">
            <pre>{`curl -X POST http://localhost:8000/api/v1/integrations/sonarqube/import \\
  -H "Authorization: Bearer vw_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "sonarqube_url": "https://sonar.example.com",
    "token": "squ_your_sonarqube_token",
    "quality_profile": "your-profile-name",
    "language": "python"
  }'`}</pre>
          </div>
          <p className="text-xs text-muted-foreground">
            For SonarCloud, use{" "}
            <code className="bg-muted px-1.5 py-0.5 rounded font-mono">
              https://sonarcloud.io
            </code>{" "}
            as the URL and a SonarCloud user token.
          </p>
        </div>

        <div className="rounded-sm border border-border p-4 space-y-1">
          <h4 className="font-semibold text-foreground text-sm">
            Mapping Report
          </h4>
          <p className="text-sm text-muted-foreground">
            After import, VigilWeave produces a mapping report with three
            categories:
          </p>
          <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
            <li>
              <strong>Matched</strong> &mdash; SonarQube rules that have a
              direct equivalent in VigilWeave&rsquo;s built-in rule set.
            </li>
            <li>
              <strong>Unmatched</strong> &mdash; Rules with no equivalent.
              These are stored as custom rules and applied during scans.
            </li>
            <li>
              <strong>Conflicts</strong> &mdash; Rules where severity or
              configuration differs between SonarQube and VigilWeave defaults.
              You can resolve these in the Tooling settings.
            </li>
          </ul>
        </div>
      </section>

      {/* Tool Configuration */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Engine Configuration
        </h3>
        <p className="text-muted-foreground">
          Every managed analyzer registered in VigilWeave can be individually
          configured. Navigate to <strong>Settings → Tooling</strong> to view
          and manage all analyzers.
        </p>

        <div className="rounded-sm border border-border p-4 space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            Managed analyzer walkthrough
          </h4>
          <ol className="list-decimal list-inside space-y-1 text-sm text-muted-foreground">
            <li>Open <strong>Settings → Tooling</strong> to review the built-in analyzer set for your tenant.</li>
            <li>Adjust categories, language targeting, and rules JSON only when you need organization-specific tuning.</li>
            <li>For mobile or build-based analyzers such as Android and .NET, ensure the repository contains the expected build files so the managed runtime can execute them during a scan.</li>
            <li>For custom analyzers, create a tenant analyzer entry, assign its category and languages, then connect its execution profile through the runner and rules fields.</li>
            <li>Re-run a scan after changes to confirm the analyzer mix and findings match your expectations.</li>
          </ol>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-sm border border-border p-4 space-y-1">
            <h4 className="font-semibold text-foreground text-sm">
              Enable / Disable
            </h4>
              <p className="text-sm text-muted-foreground">
              Toggle individual analyzers on or off. Disabled analyzers are skipped
              during all scan types. Use this to reduce scan time or remove
              analyzers that are not relevant to your tech stack.
              </p>
          </div>
          <div className="rounded-sm border border-border p-4 space-y-1">
            <h4 className="font-semibold text-foreground text-sm">
              Language Targeting
            </h4>
              <p className="text-sm text-muted-foreground">
              Override which languages an analyzer applies to. By default,
              VigilWeave auto-detects languages in your repository and runs
              only relevant analyzers.
              </p>
          </div>
          <div className="rounded-sm border border-border p-4 space-y-1">
            <h4 className="font-semibold text-foreground text-sm">
              Rule Overrides
            </h4>
              <p className="text-sm text-muted-foreground">
              Provide a JSON rules configuration to customize which rules an
              analyzer enforces. This is useful for tuning false positive rates
              or enforcing organization-specific coding standards.
              </p>
          </div>
          <div className="rounded-sm border border-border p-4 space-y-1">
              <h4 className="font-semibold text-foreground text-sm">
              Custom Analyzers
              </h4>
              <p className="text-sm text-muted-foreground">
              Register a new analyzer by specifying its ID, category,
              supported languages, and execution profile. Any analyzer that
              produces SARIF or JSON output can be integrated behind the
              managed scan pipeline.
              </p>
          </div>
        </div>
      </section>

      {/* Custom Rule Packs */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Custom Rule Packs
        </h3>
        <p className="text-muted-foreground">
          Rule packs are JSON files that define a set of rules for a specific
          language. You can create custom rule packs to enforce
          organization-specific policies or import rules from external sources.
        </p>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            Rule Pack Format
          </h4>
          <div className="code-block">
            <pre>{`{
  "language": "python",
  "source": "custom",
  "profile_name": "my-org-python-rules",
  "rules": [
    {
      "vigilweave_rule_id": "custom:python:no-eval",
      "title": "Do not use eval()",
      "description": "eval() executes arbitrary code and is a security risk.",
      "severity": "High",
      "category": "security",
      "source": "custom",
      "source_rule_key": "no-eval",
      "enabled": true,
      "tags": ["security", "injection"]
    },
    {
      "vigilweave_rule_id": "custom:python:require-type-hints",
      "title": "Functions must include type hints",
      "description": "All public functions should have parameter and return type annotations.",
      "severity": "Low",
      "category": "maintainability",
      "source": "custom",
      "source_rule_key": "require-type-hints",
      "enabled": true,
      "tags": ["maintainability", "convention"]
    }
  ]
}`}</pre>
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            Uploading Rule Packs
          </h4>
          <div className="code-block">
            <pre>{`# Upload a custom rule pack
curl -X POST http://localhost:8000/api/v1/rulepacks \\
  -H "Authorization: Bearer vw_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d @my-org-python-rules.json`}</pre>
          </div>
          <p className="text-sm text-muted-foreground">
            Uploaded rule packs are stored per-tenant and applied automatically
            during scans when the matching language is detected.
          </p>
        </div>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            Rule Fields Reference
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border border-border rounded-sm overflow-hidden">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">
                    Field
                  </th>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">
                    Required
                  </th>
                  <th className="text-left px-4 py-2 font-semibold text-foreground">
                    Description
                  </th>
                </tr>
              </thead>
              <tbody className="text-muted-foreground divide-y divide-border">
                <tr>
                  <td className="px-4 py-2 font-mono text-xs">
                    vigilweave_rule_id
                  </td>
                  <td className="px-4 py-2">Yes</td>
                  <td className="px-4 py-2">
                    Unique ID, e.g.{" "}
                    <code className="bg-muted px-1 rounded font-mono text-xs">
                      custom:python:no-eval
                    </code>
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs">title</td>
                  <td className="px-4 py-2">Yes</td>
                  <td className="px-4 py-2">
                    Short human-readable rule name
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs">severity</td>
                  <td className="px-4 py-2">Yes</td>
                  <td className="px-4 py-2">
                    Critical, High, Medium, Low, or Info
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs">category</td>
                  <td className="px-4 py-2">Yes</td>
                  <td className="px-4 py-2">
                    security, maintainability, reliability, or performance
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs">description</td>
                  <td className="px-4 py-2">No</td>
                  <td className="px-4 py-2">
                    Detailed explanation shown in findings
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs">tags</td>
                  <td className="px-4 py-2">No</td>
                  <td className="px-4 py-2">
                    String array for filtering and grouping
                  </td>
                </tr>
                <tr>
                  <td className="px-4 py-2 font-mono text-xs">enabled</td>
                  <td className="px-4 py-2">No</td>
                  <td className="px-4 py-2">
                    Defaults to true; set false to define but not enforce
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Policy Presets */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">
          Built-in Policy Presets
        </h3>
        <p className="text-muted-foreground">
          VigilWeave includes three policy presets that define quality gate
          thresholds. These can be applied per-project or organization-wide.
        </p>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-sm border border-border p-4 space-y-1">
            <h4 className="font-semibold text-foreground text-sm">Lenient</h4>
            <p className="text-sm text-muted-foreground">
              Allows up to 5 high and 20 medium findings. Suitable for early
              adoption when teams are ramping up security practices.
            </p>
          </div>
          <div className="rounded-sm border border-border p-4 space-y-1">
            <h4 className="font-semibold text-foreground text-sm">Balanced</h4>
            <p className="text-sm text-muted-foreground">
              Zero critical, up to 2 high, and 10 medium findings. The default
              preset for most teams.
            </p>
          </div>
          <div className="rounded-sm border border-border p-4 space-y-1">
            <h4 className="font-semibold text-foreground text-sm">Strict</h4>
            <p className="text-sm text-muted-foreground">
              Zero critical or high findings. Any security finding blocks the
              quality gate. Recommended for production branches.
            </p>
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          For full details on creating custom policies, waivers, and audit
          trails, see the{" "}
          <button
            type="button"
            className="text-primary underline underline-offset-2"
            onClick={() => {
              const url = new URL(window.location.href);
              url.searchParams.set("section", "policy-governance");
              window.history.replaceState({}, "", url.toString());
              window.location.reload();
            }}
          >
            Policy &amp; Governance
          </button>{" "}
          documentation.
        </p>
      </section>
    </div>
  );
}
