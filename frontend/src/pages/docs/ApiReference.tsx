export function ApiReference() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">API Reference</h2>
        <p className="text-muted-foreground">
          VigilWeave exposes a RESTful JSON API for programmatic access to scans,
          findings, projects, and policies. All endpoints require authentication via
          API key.
        </p>
        <div className="rounded-sm border border-primary/20 bg-primary/5 p-4 space-y-2">
          <p className="text-sm font-semibold text-primary">
            Interactive API Explorer
          </p>
          <p className="text-sm text-muted-foreground">
            VigilWeave auto-generates an OpenAPI specification. Access the
            interactive API explorer at{" "}
            <a
              href="/api/v1/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline underline-offset-2 font-mono text-xs"
            >
              /api/v1/docs
            </a>{" "}
            (Swagger UI) or{" "}
            <a
              href="/api/v1/redoc"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline underline-offset-2 font-mono text-xs"
            >
              /api/v1/redoc
            </a>{" "}
            (ReDoc) to browse all endpoints, test requests, and view response
            schemas directly in your browser.
          </p>
        </div>
      </div>

      {/* Authentication */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Authentication</h3>
        <p className="text-muted-foreground">
          API keys are used to authenticate requests. Generate a key from{" "}
          <strong>Settings &rarr; API Keys</strong> in the dashboard. All keys are
          prefixed with{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">
            vw_
          </code>{" "}
          for easy identification.
        </p>
        <div className="code-block">
          <pre>{`# Include the API key in the Authorization header
curl -H "Authorization: Bearer vw_sk_live_abc123def456" \\
  http://localhost:8000/api/v1/projects`}</pre>
        </div>
        <div className="rounded-sm border border-yellow-500/30 bg-yellow-500/5 p-4 space-y-1">
          <p className="text-sm font-semibold text-yellow-500">Security Note</p>
          <p className="text-sm text-muted-foreground">
            Keep your API keys secret. Do not commit them to version control. Use
            environment variables or a secrets manager in CI/CD environments. Keys
            can be revoked at any time from the Settings page.
          </p>
        </div>
      </section>

      {/* Base URL */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Base URL</h3>
        <div className="code-block">
          <pre>{`# Self-hosted
http://localhost:8000/api/v1

# VigilWeave Cloud
https://app.vigilweave.com/api/v1`}</pre>
        </div>
      </section>

      {/* Projects */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Projects</h3>

        <div className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="rounded bg-blue-500/20 px-2 py-0.5 text-xs font-mono font-bold text-blue-400">GET</span>
              <code className="text-sm font-mono text-foreground">/projects</code>
            </div>
            <p className="text-sm text-muted-foreground">List all projects accessible to the authenticated user.</p>
            <div className="code-block">
              <pre>{`curl -H "Authorization: Bearer vw_your_api_key" \\
  http://localhost:8000/api/v1/projects

# Response
{
  "items": [
    {
      "id": "proj_abc123",
      "name": "payments-api",
      "repo_count": 3,
      "last_scan_at": "2026-03-20T14:30:00Z",
      "policy_id": "pol_strict01"
    }
  ],
  "total": 1,
  "page": 1
}`}</pre>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="rounded bg-success/15 px-2 py-0.5 text-xs font-mono font-bold text-success">POST</span>
              <code className="text-sm font-mono text-foreground">/projects</code>
            </div>
            <p className="text-sm text-muted-foreground">Create a new project.</p>
            <div className="code-block">
              <pre>{`curl -X POST http://localhost:8000/api/v1/projects \\
  -H "Authorization: Bearer vw_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "payments-api",
    "description": "Payment processing microservice",
    "policy_id": "pol_balanced01"
  }'`}</pre>
            </div>
          </div>
        </div>
      </section>

      {/* Scans */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Scans</h3>

        <div className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="rounded bg-success/15 px-2 py-0.5 text-xs font-mono font-bold text-success">POST</span>
              <code className="text-sm font-mono text-foreground">/scans</code>
            </div>
            <p className="text-sm text-muted-foreground">Trigger a new scan for a project.</p>
            <div className="code-block">
              <pre>{`curl -X POST http://localhost:8000/api/v1/scans \\
  -H "Authorization: Bearer vw_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "project_id": "proj_abc123",
    "scan_type": "comprehensive",
    "ref": "main"
  }'

# Response
{
  "id": "scan_xyz789",
  "status": "queued",
  "project_id": "proj_abc123",
  "scan_type": "comprehensive",
  "created_at": "2026-03-20T14:35:00Z"
}`}</pre>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="rounded bg-blue-500/20 px-2 py-0.5 text-xs font-mono font-bold text-blue-400">GET</span>
              <code className="text-sm font-mono text-foreground">/scans/{'{scan_id}'}</code>
            </div>
            <p className="text-sm text-muted-foreground">Get scan details and status.</p>
            <div className="code-block">
              <pre>{`curl -H "Authorization: Bearer vw_your_api_key" \\
  http://localhost:8000/api/v1/scans/scan_xyz789

# Response
{
  "id": "scan_xyz789",
  "status": "completed",
  "project_id": "proj_abc123",
  "scan_type": "comprehensive",
  "finding_counts": {
    "critical": 0,
    "high": 2,
    "medium": 5,
    "low": 12
  },
  "gate_result": "pass",
  "duration_seconds": 47,
  "created_at": "2026-03-20T14:35:00Z",
  "completed_at": "2026-03-20T14:35:47Z"
}`}</pre>
            </div>
          </div>
        </div>
      </section>

      {/* Findings */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Findings</h3>

        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="rounded bg-blue-500/20 px-2 py-0.5 text-xs font-mono font-bold text-blue-400">GET</span>
            <code className="text-sm font-mono text-foreground">/findings</code>
          </div>
          <p className="text-sm text-muted-foreground">
            List findings with filtering and pagination. Supports query parameters for
            project, scan, severity, status, tool, and CWE.
          </p>
          <div className="code-block">
            <pre>{`# List critical and high findings for a project
curl -H "Authorization: Bearer vw_your_api_key" \\
  "http://localhost:8000/api/v1/findings?project_id=proj_abc123&severity=critical,high&status=open"

# Response
{
  "items": [
    {
      "id": "fnd_001",
      "title": "SQL Injection via string concatenation",
      "severity": "high",
      "status": "open",
      "engine": "sast",
      "rule_id": "python.django.security.injection.sql",
      "file_path": "app/api/users.py",
      "line_start": 42,
      "line_end": 42,
      "cwe_id": "CWE-89",
      "created_at": "2026-03-20T14:35:30Z"
    }
  ],
  "total": 2,
  "page": 1
}`}</pre>
          </div>
        </div>
      </section>

      {/* Policies */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Policies</h3>

        <div className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="rounded bg-blue-500/20 px-2 py-0.5 text-xs font-mono font-bold text-blue-400">GET</span>
              <code className="text-sm font-mono text-foreground">/policies</code>
            </div>
            <p className="text-sm text-muted-foreground">List all policies including built-in presets and custom policies.</p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="rounded bg-success/15 px-2 py-0.5 text-xs font-mono font-bold text-success">POST</span>
              <code className="text-sm font-mono text-foreground">/policies</code>
            </div>
            <p className="text-sm text-muted-foreground">Create a custom quality gate policy.</p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="rounded bg-orange-500/20 px-2 py-0.5 text-xs font-mono font-bold text-orange-400">PUT</span>
              <code className="text-sm font-mono text-foreground">/policies/{'{policy_id}'}</code>
            </div>
            <p className="text-sm text-muted-foreground">Update an existing policy. Built-in presets cannot be modified.</p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="rounded bg-red-500/20 px-2 py-0.5 text-xs font-mono font-bold text-red-400">DELETE</span>
              <code className="text-sm font-mono text-foreground">/policies/{'{policy_id}'}</code>
            </div>
            <p className="text-sm text-muted-foreground">
              Delete a custom policy. Projects using this policy will fall back to the
              default Balanced preset.
            </p>
          </div>
        </div>
      </section>

      {/* Rate Limits */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Rate Limits</h3>
        <p className="text-muted-foreground">
          API requests are rate-limited per API key. Current limits are:
        </p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground">
          <li><strong>Free tier:</strong> 100 requests per minute, 10 scans per day</li>
          <li><strong>Pro tier:</strong> 1,000 requests per minute, 100 scans per day</li>
          <li><strong>Enterprise / Self-hosted:</strong> Unlimited</li>
        </ul>
        <p className="text-sm text-muted-foreground">
          Rate limit headers (
          <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">X-RateLimit-Remaining</code>,{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">X-RateLimit-Reset</code>
          ) are included in every response.
        </p>
      </section>
    </div>
  );
}
