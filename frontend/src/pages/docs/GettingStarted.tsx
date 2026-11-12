import { DOWNLOADS_URL } from "../../lib/public-links";

export function GettingStarted() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">Getting Started</h2>
        <p className="text-muted-foreground">
          Get VigilWeave up and running in under five minutes. This guide walks you
          through installation, basic configuration, and running your first security
          scan.
        </p>
      </div>

      {/* Prerequisites */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Prerequisites</h3>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground">
          <li>Docker 24+ and Docker Compose v2</li>
          <li>At least 4 GB of available RAM</li>
          <li>A GitHub, GitLab, or Azure DevOps account (for repository imports)</li>
          <li>Node.js 18+ (only if running the frontend outside Docker)</li>
        </ul>
      </section>

      {/* Quick Start with Docker */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Quick Start with Docker</h3>
        <p className="text-muted-foreground">
          The fastest way to get started is with Docker Compose. Download the
          Community release bundle, unpack it, and start all services with a
          single command:
        </p>
        <div className="code-block">
          <pre>{`# Download the Community release bundle
curl -L ${DOWNLOADS_URL} -o vigilweave-community.tar.gz
tar -xzf vigilweave-community.tar.gz
cd vigilweave-community

# Copy the example environment file
cp .env.example .env

# Start all services (API, frontend, database, worker)
docker compose up -d`}</pre>
        </div>
        <p className="text-muted-foreground">
          Once the containers are running, open{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">
            http://localhost:5173
          </code>{" "}
          in your browser to access the dashboard.
        </p>
      </section>

      {/* Environment Variables */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Environment Variables</h3>
        <p className="text-muted-foreground">
          The{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">
            .env
          </code>{" "}
          file controls core behavior. Here are the most important variables:
        </p>
        <div className="code-block">
          <pre>{`# Database
DATABASE_URL=postgresql://vigilweave:vigilweave@db:5432/vigilweave

# API server
API_HOST=0.0.0.0
API_PORT=8000
SESSION_AUTH_PROVIDER=local
API_KEYS_ENABLED=true
SESSION_SECRET=change-me-to-a-random-string

# Git repository integration (optional)
GITHUB_APP_ID=
GITHUB_PRIVATE_KEY_PATH=

# Commercial self-hosted entitlement (paid plans only)
LICENSE_KEY=

# WorkOS SSO (commercial deployments only)
WORKOS_API_KEY=
WORKOS_CLIENT_ID=`}</pre>
        </div>
        <p className="text-sm text-muted-foreground">
          At minimum, set{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">
            SESSION_SECRET
          </code>{" "}
          to a secure random value before deploying to production.
        </p>
      </section>

      {/* Basic Configuration */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Basic Configuration</h3>
        <p className="text-muted-foreground">
          After first launch, VigilWeave will guide you through an onboarding flow:
        </p>
        <ol className="list-decimal list-inside space-y-2 text-muted-foreground">
          <li>
            <strong>Create your account</strong> &mdash; Complete the first-run
            local admin setup with an email and password.
          </li>
          <li>
            <strong>Create a project</strong> &mdash; A project groups related
            repositories and scans under one umbrella.
          </li>
          <li>
            <strong>Connect repositories</strong> &mdash; Link one or more Git
            repositories via HTTPS URL or an integration such as GitHub App or
            Azure DevOps.
          </li>
          <li>
            <strong>Choose a policy</strong> &mdash; Select a built-in quality gate
            (Lenient, Balanced, or Strict) or create a custom policy later.
          </li>
        </ol>
      </section>

      {/* First Scan Walkthrough */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Running Your First Scan</h3>
        <p className="text-muted-foreground">
          Once a project is set up, kick off a scan from the dashboard or the CLI:
        </p>
        <div className="code-block">
          <pre>{`# From the UI
# Navigate to Projects → your project → "New Scan"
# Select scan types (SAST, Secrets, Dependencies, IaC)
# Click "Start Scan"

# Or via the API
curl -X POST http://localhost:8000/api/v1/scans \\
  -H "Authorization: Bearer vw_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "project_id": "proj_abc123",
    "scan_type": "comprehensive",
    "ref": "main"
  }'`}</pre>
        </div>
        <p className="text-muted-foreground">
          Scans typically complete in 30&ndash;120 seconds depending on repository
          size and the number of enabled scan types. Results appear in the dashboard
          as each analysis completes.
        </p>
      </section>

      {/* Next Steps */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Next Steps</h3>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground">
          <li>Explore the <strong>Scanning</strong> docs to learn about supported tools and triage workflows.</li>
          <li>Set up <strong>Policy &amp; Governance</strong> rules to enforce quality gates on every commit.</li>
          <li>Configure <strong>Integrations</strong> to run scans automatically in your CI/CD pipeline.</li>
          <li>Generate your first <strong>API key</strong> under Settings &rarr; API Keys for programmatic access.</li>
        </ul>
      </section>
    </div>
  );
}
