import { DOWNLOADS_URL } from "../../lib/public-links";

export function SelfHosting() {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-foreground mb-2">Self-Hosting</h2>
        <p className="text-muted-foreground">
          Run VigilWeave entirely on your own infrastructure. This guide covers
          Docker Compose setup, environment configuration, database management,
          upgrades, and commercial deployment options.
        </p>
      </div>

      {/* Docker Compose Setup */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Docker Compose Setup</h3>
        <p className="text-muted-foreground">
          The recommended way to self-host VigilWeave is with Docker Compose.
          Community release bundles ship with a compose file for local-user auth,
          API access, and the worker services needed to run scans.
        </p>
        <div className="code-block">
          <pre>{`# Download the Community release bundle
curl -L ${DOWNLOADS_URL} -o vigilweave-community.tar.gz
tar -xzf vigilweave-community.tar.gz
cd vigilweave-community

# Copy the example environment file
cp .env.example .env

# Start the stack
docker compose up -d`}</pre>
        </div>
        <div className="code-block">
          <pre>{`# View logs
docker compose logs -f api

# Stop the stack
docker compose down`}</pre>
        </div>
        <p className="text-sm text-muted-foreground">
          Paid self-hosted customers receive commercial release artifacts or
          private registry credentials separately from the public Community
          download flow.
        </p>
      </section>

      {/* Docker Compose Files */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Docker Compose Configuration</h3>
        <p className="text-muted-foreground">
          The Community stack consists of four services: Redis (job queue), API
          (FastAPI), Worker (Celery scanner), and Frontend (Nginx). Save the file
          below as{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded-sm text-sm font-mono">
            docker-compose.yml
          </code>{" "}
          in your project directory.
        </p>

        <h4 className="text-base font-semibold text-foreground">docker-compose.yml</h4>
        <div className="code-block">
          <pre>{`services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    image: vigilweave/api:latest
    environment:
      DATABASE_URL: sqlite:////data/vigilweave.db
      REDIS_URL: redis://redis:6379/0
      CELERY_TASK_ALWAYS_EAGER: "false"
      HOST_REPO_ROOT: \${VIGILWEAVE_HOST_REPO_ROOT:-}
      CONTAINER_REPO_ROOT: \${VIGILWEAVE_CONTAINER_REPO_ROOT:-/workspace}
      SESSION_AUTH_PROVIDER: \${SESSION_AUTH_PROVIDER:-local}
      API_KEYS_ENABLED: \${API_KEYS_ENABLED:-true}
      SESSION_SECRET: \${SESSION_SECRET:-}
    volumes:
      - vigilweave_data:/data
      - \${VIGILWEAVE_HOST_REPO_ROOT:-.}:\${VIGILWEAVE_CONTAINER_REPO_ROOT:-/workspace}:ro
    ports:
      - "\${API_HOST_PORT:-8000}:8000"
    depends_on:
      - redis

  worker:
    image: vigilweave/api:latest
    command: >-
      celery -A app.core.celery_app.celery_app worker
      --loglevel=info --concurrency=\${CELERY_CONCURRENCY:-2}
    environment:
      DATABASE_URL: sqlite:////data/vigilweave.db
      REDIS_URL: redis://redis:6379/0
      CELERY_TASK_ALWAYS_EAGER: "false"
      TOOLCHAIN_PROFILE: \${TOOLCHAIN_PROFILE:-base}
      HOST_REPO_ROOT: \${VIGILWEAVE_HOST_REPO_ROOT:-}
      CONTAINER_REPO_ROOT: \${VIGILWEAVE_CONTAINER_REPO_ROOT:-/workspace}
      SESSION_AUTH_PROVIDER: \${SESSION_AUTH_PROVIDER:-local}
      API_KEYS_ENABLED: \${API_KEYS_ENABLED:-true}
    volumes:
      - vigilweave_data:/data
      - \${VIGILWEAVE_HOST_REPO_ROOT:-.}:\${VIGILWEAVE_CONTAINER_REPO_ROOT:-/workspace}:ro
    depends_on:
      - redis
    deploy:
      replicas: \${WORKER_REPLICAS:-1}

  frontend:
    image: vigilweave/frontend:latest
    ports:
      - "\${FRONTEND_HOST_PORT:-8080}:80"
    depends_on:
      - api

volumes:
  vigilweave_data:`}</pre>
        </div>

        <h4 className="text-base font-semibold text-foreground mt-6">docker-compose.enterprise.yml (overlay)</h4>
        <p className="text-muted-foreground">
          For commercial deployments with WorkOS SSO and the extended toolchain,
          layer this override file on top of the base compose file:
        </p>
        <div className="code-block">
          <pre>{`# docker-compose.enterprise.yml
services:
  api:
    image: vigilweave/api:latest-enterprise
    environment:
      TOOLCHAIN_PROFILE: enterprise
      SESSION_AUTH_PROVIDER: \${SESSION_AUTH_PROVIDER:-workos}
      API_KEYS_ENABLED: \${API_KEYS_ENABLED:-true}
      SAAS_ENABLED: \${SAAS_ENABLED:-true}
      SAAS_DOMAIN: \${SAAS_DOMAIN:-app.vigilweave.com}
      SESSION_SECRET: \${SESSION_SECRET:-}
      WORKOS_API_KEY: \${WORKOS_API_KEY:-}
      WORKOS_CLIENT_ID: \${WORKOS_CLIENT_ID:-}
      WORKOS_REDIRECT_URI: \${WORKOS_REDIRECT_URI:-http://localhost:8000/api/v1/auth/callback}
      WORKOS_COOKIE_DOMAIN: \${WORKOS_COOKIE_DOMAIN:-localhost}
      WORKOS_SESSION_SECRET: \${WORKOS_SESSION_SECRET:-}

  worker:
    image: vigilweave/api:latest-enterprise
    command: >-
      celery -A app.core.celery_app.celery_app worker
      --loglevel=info --concurrency=\${CELERY_CONCURRENCY:-4}
    environment:
      TOOLCHAIN_PROFILE: enterprise
      SESSION_AUTH_PROVIDER: \${SESSION_AUTH_PROVIDER:-workos}
      API_KEYS_ENABLED: \${API_KEYS_ENABLED:-true}
    deploy:
      replicas: \${WORKER_REPLICAS:-2}`}</pre>
        </div>
        <div className="code-block">
          <pre>{`# Start with enterprise overlay
docker compose -f docker-compose.yml -f docker-compose.enterprise.yml up -d`}</pre>
        </div>
      </section>

      {/* Kubernetes Deployment */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Kubernetes Deployment</h3>
        <p className="text-muted-foreground">
          For teams that need horizontal scaling, high availability, or integration
          with existing cluster infrastructure, VigilWeave can be deployed to
          Kubernetes. Docker Compose is still recommended for most deployments.
        </p>
        <p className="text-muted-foreground">
          VigilWeave maps to four Kubernetes Deployments: <strong>API</strong> (FastAPI/uvicorn),{" "}
          <strong>Worker</strong> (Celery), <strong>Frontend</strong> (Nginx), and{" "}
          <strong>Redis</strong> (or use a managed service). A single Ingress routes{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded-sm text-sm font-mono">/api/</code> to
          the API and <code className="bg-muted px-1.5 py-0.5 rounded-sm text-sm font-mono">/</code> to
          the frontend.
        </p>
        <div className="code-block">
          <pre>{`# Apply all manifests
kubectl apply -f namespace.yaml
kubectl apply -f secrets.yaml
kubectl apply -f configmap.yaml
kubectl apply -f redis.yaml
kubectl apply -f api.yaml
kubectl apply -f worker.yaml
kubectl apply -f frontend.yaml
kubectl apply -f ingress.yaml

# Verify
kubectl get pods -n vigilweave`}</pre>
        </div>
        <p className="text-sm text-muted-foreground">
          For the full Kubernetes deployment guide with complete manifest files, scaling
          configuration, and enterprise setup, see{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded-sm text-sm font-mono">
            docs/kubernetes-deployment.md
          </code>{" "}
          in the project root.
        </p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground">
          <li>PostgreSQL is required for multi-replica API deployments (SQLite is single-replica only).</li>
          <li>Workers scale independently based on scan workload via HPA.</li>
          <li>The frontend image bakes in the API URL at build time via <code className="bg-muted px-1.5 py-0.5 rounded-sm text-sm font-mono">VITE_API_BASE_URL</code>.</li>
          <li>Enterprise deployments use the <code className="bg-muted px-1.5 py-0.5 rounded-sm text-sm font-mono">runtime-enterprise</code> build target for extended toolchain.</li>
        </ul>
      </section>

      {/* Environment Variables */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Environment Variables Reference</h3>
        <p className="text-muted-foreground">
          Complete list of environment variables supported by the API server:
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border rounded-sm overflow-hidden">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-2 font-semibold text-foreground">Variable</th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">Required</th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">Default</th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">Description</th>
              </tr>
            </thead>
            <tbody className="text-muted-foreground divide-y divide-border">
              <tr>
                <td className="px-4 py-2 font-mono text-xs">DATABASE_URL</td>
                <td className="px-4 py-2">Yes</td>
                <td className="px-4 py-2">&mdash;</td>
                <td className="px-4 py-2">PostgreSQL connection string</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">REDIS_URL</td>
                <td className="px-4 py-2">No</td>
                <td className="px-4 py-2">redis://localhost:6379/0</td>
                <td className="px-4 py-2">Redis connection for job queue and caching</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">SESSION_AUTH_PROVIDER</td>
                <td className="px-4 py-2">Yes</td>
                <td className="px-4 py-2">local</td>
                <td className="px-4 py-2">Browser session provider: none, local, or workos</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">API_KEYS_ENABLED</td>
                <td className="px-4 py-2">No</td>
                <td className="px-4 py-2">true</td>
                <td className="px-4 py-2">Enables header-based API keys for automation clients</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">SESSION_SECRET</td>
                <td className="px-4 py-2">Yes</td>
                <td className="px-4 py-2">&mdash;</td>
                <td className="px-4 py-2">Random string for signing browser sessions</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">LICENSE_KEY</td>
                <td className="px-4 py-2">Paid only</td>
                <td className="px-4 py-2">&mdash;</td>
                <td className="px-4 py-2">Commercial entitlement key for paid self-hosted plans</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">API_HOST</td>
                <td className="px-4 py-2">No</td>
                <td className="px-4 py-2">0.0.0.0</td>
                <td className="px-4 py-2">Host to bind the API server</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">API_PORT</td>
                <td className="px-4 py-2">No</td>
                <td className="px-4 py-2">8000</td>
                <td className="px-4 py-2">Port for the API server</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">SAAS_ENABLED</td>
                <td className="px-4 py-2">No</td>
                <td className="px-4 py-2">false</td>
                <td className="px-4 py-2">Enables SaaS-specific runtime behavior for hosted deployments</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">GITHUB_APP_ID</td>
                <td className="px-4 py-2">No</td>
                <td className="px-4 py-2">&mdash;</td>
                <td className="px-4 py-2">GitHub App ID for repository integration</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">GITHUB_PRIVATE_KEY_PATH</td>
                <td className="px-4 py-2">No</td>
                <td className="px-4 py-2">&mdash;</td>
                <td className="px-4 py-2">Path to GitHub App private key PEM file</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">WORKOS_API_KEY</td>
                <td className="px-4 py-2">No</td>
                <td className="px-4 py-2">&mdash;</td>
                <td className="px-4 py-2">WorkOS API key for commercial SSO deployments</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">WORKOS_CLIENT_ID</td>
                <td className="px-4 py-2">No</td>
                <td className="px-4 py-2">&mdash;</td>
                <td className="px-4 py-2">WorkOS Client ID for commercial SSO deployments</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">WORKOS_REDIRECT_URI</td>
                <td className="px-4 py-2">No</td>
                <td className="px-4 py-2">http://localhost:8000/api/v1/auth/callback</td>
                <td className="px-4 py-2">Callback URI registered with WorkOS</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">LOG_LEVEL</td>
                <td className="px-4 py-2">No</td>
                <td className="px-4 py-2">info</td>
                <td className="px-4 py-2">Logging level: debug, info, warning, error</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Database Configuration */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Database Configuration</h3>
        <p className="text-muted-foreground">
          VigilWeave requires PostgreSQL 14 or later. The database schema is managed
          via Alembic migrations that run automatically on startup.
        </p>
        <div className="code-block">
          <pre>{`# Run migrations manually (if auto-migration is disabled)
docker compose exec api alembic upgrade head

# Check current migration version
docker compose exec api alembic current

# Create a database backup
docker compose exec db pg_dump -U vigilweave vigilweave > backup.sql

# Restore from backup
docker compose exec -T db psql -U vigilweave vigilweave < backup.sql`}</pre>
        </div>
        <p className="text-sm text-muted-foreground">
          For production deployments, use a managed PostgreSQL service (AWS RDS,
          Azure Database for PostgreSQL, Google Cloud SQL) and configure the{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono">
            DATABASE_URL
          </code>{" "}
          accordingly.
        </p>
      </section>

      {/* Upgrades */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Upgrades</h3>
        <p className="text-muted-foreground">
          To upgrade to a new version of VigilWeave:
        </p>
        <div className="code-block">
          <pre>{`# 1. Pull the latest images referenced by your compose files
docker compose pull

# 2. Restart services (migrations run automatically)
docker compose up -d

# 3. Verify the new version
curl http://localhost:8000/api/v1/system/health
# {"status":"ok","version":"2.0.0"}`}</pre>
        </div>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground">
          <li>Always back up your database before upgrading.</li>
          <li>Check the release notes for breaking changes or required manual migration steps.</li>
          <li>Downgrades are not officially supported. Restore from backup if needed.</li>
        </ul>
      </section>

      {/* Commercial Deployment with WorkOS */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Commercial Deployment with WorkOS</h3>
        <p className="text-muted-foreground">
          Commercial SaaS and self-hosted deployments can enable WorkOS-backed
          browser sessions for SSO. Community defaults to built-in local users.
        </p>
        <div className="code-block">
          <pre>{`# Apply the commercial / SaaS override
docker compose -f docker-compose.yml -f docker-compose.enterprise.yml up -d

# Required environment variables for WorkOS
SESSION_AUTH_PROVIDER=workos
API_KEYS_ENABLED=true
SAAS_ENABLED=true
WORKOS_API_KEY=YOUR_WORKOS_API_KEY_HERE
WORKOS_CLIENT_ID=YOUR_WORKOS_CLIENT_ID_HERE
WORKOS_REDIRECT_URI=https://your-domain.com/api/v1/auth/callback
SESSION_SECRET=YOUR_SESSION_SECRET_HERE`}</pre>
        </div>
        <p className="text-muted-foreground">
          Commercial deployments typically also include:
        </p>
        <ul className="list-disc list-inside space-y-1 text-muted-foreground">
          <li>WorkOS-backed authentication for hosted or approved self-hosted deployments</li>
          <li>Commercial entitlements for reporting and advanced workflows</li>
          <li>Private distribution for paid self-hosted plans</li>
          <li>Commercial onboarding and support terms</li>
        </ul>
      </section>

      {/* Monitoring & Observability */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Monitoring & Observability</h3>
        <p className="text-muted-foreground">
          VigilWeave exposes metrics for monitoring scan performance, worker
          health, and system resource usage.
        </p>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            Prometheus Endpoint
          </h4>
          <p className="text-sm text-muted-foreground">
            Scrape metrics in Prometheus exposition format from the admin-only
            endpoint:
          </p>
          <div className="code-block">
            <pre>{`# Prometheus scrape config
scrape_configs:
  - job_name: vigilweave
    scheme: http
    metrics_path: /api/v1/system/metrics/prometheus
    authorization:
      credentials: vw_your_admin_api_key
    static_configs:
      - targets: ['localhost:8000']`}</pre>
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            JSON Metrics
          </h4>
          <p className="text-sm text-muted-foreground">
            For custom dashboards, the JSON metrics endpoint returns counters
            and timer aggregates:
          </p>
          <div className="code-block">
            <pre>{`curl -H "Authorization: Bearer vw_your_admin_api_key" \\
  http://localhost:8000/api/v1/system/metrics`}</pre>
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            Tool Telemetry
          </h4>
          <p className="text-sm text-muted-foreground">
            View per-engine execution statistics (run counts, avg duration,
            failure rates) from the Settings &rarr; Monitoring tab or via the
            API:
          </p>
          <div className="code-block">
            <pre>{`curl -H "Authorization: Bearer YOUR_API_KEY_HERE" \\
  http://localhost:8000/api/v1/system/tool-telemetry`}</pre>
          </div>
        </div>

        <div className="space-y-2">
          <h4 className="font-semibold text-foreground text-sm">
            Celery Worker Limits
          </h4>
          <p className="text-sm text-muted-foreground">
            Workers are configured with resource isolation to prevent runaway
            scans:
          </p>
          <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
            <li><strong>Hard kill:</strong> 30 minutes per task</li>
            <li><strong>Soft limit:</strong> 25 minutes (raises SoftTimeLimitExceeded for graceful cleanup)</li>
            <li><strong>Worker recycling:</strong> After 50 tasks per worker process</li>
            <li><strong>Memory cap:</strong> 2 GB max per worker process</li>
          </ul>
        </div>
      </section>

      {/* Domain Architecture */}
      <section className="space-y-3">
        <h3 className="text-xl font-semibold text-foreground">Domain Architecture</h3>
        <p className="text-muted-foreground">
          VigilWeave SaaS uses two domains:
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border border-border rounded-sm overflow-hidden">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left px-4 py-2 font-semibold text-foreground">Domain</th>
                <th className="text-left px-4 py-2 font-semibold text-foreground">Purpose</th>
              </tr>
            </thead>
            <tbody className="text-muted-foreground divide-y divide-border">
              <tr>
                <td className="px-4 py-2 font-mono text-xs">vigilweave.com</td>
                <td className="px-4 py-2">Marketing site, pricing, documentation, downloads, legal</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">app.vigilweave.com</td>
                <td className="px-4 py-2">Application dashboard, API, authenticated services</td>
              </tr>
              <tr>
                <td className="px-4 py-2 font-mono text-xs">license.vigilweave.com</td>
                <td className="px-4 py-2">License verification server</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-sm text-muted-foreground">
          Self-hosted deployments serve everything from a single origin (e.g.{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded-sm text-sm font-mono">
            http://localhost:8000
          </code>
          ). The API lives at{" "}
          <code className="bg-muted px-1.5 py-0.5 rounded-sm text-sm font-mono">
            /api/v1/...
          </code>{" "}
          on the same host as the frontend.
        </p>
      </section>
    </div>
  );
}
