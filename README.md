# VigilWeave

VigilWeave is an attempt to build an open-source, self-hostable alternative to code-quality
and security platforms such as SonarQube. The goal is to bring repository scanning,
actionable findings, quality gates, and reporting into one platform that developers can
run, inspect, and improve themselves.

The project is still under development. It is a way to learn how these platforms work while
building an open-source alternative, not a claim of feature parity or production readiness.
For now, use synthetic data and disposable test credentials in a controlled environment.
Do not connect production systems or upload customer data. Existing edition controls remain
in the codebase; local feature access is documented below.

VigilWeave scans repositories for security vulnerabilities, secret leaks, dependency risks,
infrastructure-as-code misconfiguration, and code quality issues, then presents the results
through a web dashboard, a REST API, CI/CD integrations, IDE extensions, and an MCP server.

VigilWeave is an independent project and is not affiliated with or endorsed by SonarSource.

Released under the [MIT License](LICENSE).

---

## Capabilities

| Area | Scope |
|------|-------|
| **Scan** | 12+ scanners (SAST, secrets, IaC, dependencies) in one pass |
| **Policy** | Quality gates, custom policies, waivers, audit trail |
| **Reports** | PDF reports, CSV/Excel export, compliance matrices |
| **MCP** | Model Context Protocol tools for AI-assisted security triage |

## Architecture

- **Backend**: FastAPI + Celery workers, SQLModel persistence (SQLite by default, PostgreSQL supported)
- **Frontend**: React 19 + Vite 8 + Tailwind CSS v4 + HeroUI v3 (public pages) + shadcn/ui (dashboard) + framer-motion
- **Deployment**: Docker Compose, or any container platform
- **Auth**: Local username/password by default, WorkOS AuthKit for SSO deployments

## Quick Start

For the source-only core application, see the [core setup guide](docs/core-application.md).
Create its ZIP with `python3 scripts/package_core.py`. Dependencies, generated builds,
tests and separate integration projects are not included in that archive.

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
bun install
bun run dev
```

### Docker

```bash
docker compose up -d --build
# Open http://localhost:5173
```

Self-hosted deployments default to built-in local-user browser sessions.
API keys are available in **Settings > API Keys** for CI, scripts, and IDE integrations.

### Local Development With All Features

Feature gating defaults to the community tier. To unlock every feature while developing locally:

```bash
# .env
SESSION_AUTH_PROVIDER=local
LICENSE_TESTING_MODE=true
API_KEYS_ENABLED=true
```

This bypasses license verification and grants the highest feature tier. No external license server
or network access is required.

1. Start backend + frontend (`uvicorn` + `bun run dev`)
2. Visit `http://localhost:5173`
3. Click **Set Up Admin** and create your local admin account
4. Complete onboarding to reach the Projects page
5. Add SCM connections under **Settings → Connections** (GitHub, GitLab, Bitbucket, Azure DevOps)
6. Create a project and import repositories from your connected SCM accounts

See the [SCM provider API reference](docs/scm-providers-api.md) for authentication,
permissions, discovery endpoints, pagination, clone credentials and troubleshooting.

### Upgrading to 4.0

- Browser cookies now expire on the server. Access sessions last 24 hours; WorkOS refresh
  cookies last seven days. Logout signs out all browser sessions for that user, and security
  changes revoke existing sessions. The migration requires a one-time sign-in. Configure
  `SESSION_SECRET` for development sessions that must survive restarts or multiple processes;
  without it, development and test servers use a random secret for each process.
- Git credentials are passed through transient repository-scoped configuration, and clone
  arguments and saved remotes omit credentials. Branches must be valid Git branch names;
  explicit commits require 7–64 hexadecimal characters. GitHub webhooks require a stored
  tenant installation and a repository link for that installation. Azure pull-request hooks
  currently return 503 until tenant-owned subscription credentials are implemented.
- Scanner processes receive a minimal environment and temporary HOME. Affected scanners
  ignore repository configuration; temporary caches can require repeated downloads and
  reduce offline functionality. Older tools may reject required flags. This is not an OS
  sandbox: scanners retain the worker's filesystem, network and process privileges.
- A selected analyser that skips or fails, or a scan with no completed analyser, fails the
  gate. Custom scans require enabled analyser IDs. Invalid SARIF and incomplete Bandit,
  Semgrep, Ruff, Checkov, ESLint, SQLFluff, SwiftLint and Android reports cannot count as
  successful analysis. Failed Android/.NET builds retain valid report findings but fail execution.
- Complexity findings identify individual Lizard functions. Scan-level duplication is
  unmeasured and is reported as unknown. The debt estimate remains a heuristic.
- New findings use versioned repository-relative identities. Legacy native waivers need an
  exact rule constraint to match a compatibility alias; review fingerprint-only native waivers
  before upgrading. Existing quality complexity waivers continue to cover the file's functions.
  Triage carries between completed scans of the same tenant, assigned project, repository and
  branch; previously fixed issues reopen. Identical repeated occurrences can change identity
  when another identical occurrence is inserted earlier. Old scan records are not rewritten.
- Finding diagnostic text and known sensitive metadata fields receive best-effort redaction
  before repository and IDE results are returned or stored. This cannot detect every secret.
  Partial findings from failed tools are retained, while incomplete coverage still fails the gate.

### Upgrading to 3.0

- API-key creation requires admin authority, including the first key created by an
  authenticated user. The existing anonymous development bootstrap still applies.
- WorkOS tokens must have a supported issuer and a subject. An audience, when supplied,
  must include the configured client ID.
- Linked SCM clones must stay on the configured provider origin. Azure DevOps clones
  must also stay in the configured organisation. Invalid or inactive credential links fail
  the scan instead of falling back silently.
- Failed or unfinished scanner executions prevent a passing gate. An assigned project
  policy supplies the thresholds; deployment defaults apply when no policy is selected.
- Source excerpts omit secret findings and files with detected secrets, reject paths
  outside the checkout, and skip files larger than 1 MiB. Other excerpts receive best-effort
  redaction; this does not guarantee that all secrets are removed.
- ESLint now shares the repository-code execution opt-in with Gradle and .NET adapters:
  `ENABLE_REPO_BUILD_TOOL_ADAPTERS=true`. Enable it only for trusted repositories.
  This reduces default JS/TS lint coverage. These controls do not provide a scanner sandbox.
- `LICENSE_TESTING_MODE=true` is restricted to development/test. Cached licences cannot
  grant access past expiry; explicit rejection clears the previous positive cache entry.

## Worker

```bash
source .venv/bin/activate
celery -A app.core.celery_app.celery_app worker --loglevel=info
```

Queued scans are claimed once with a database token. Workers send heartbeats, and the API
marks expired workers' scans as failed with an interruption reason. Tool diagnostics survive
finalisation failures; findings, metrics, waivers and successful completion commit together.
Broker submission failures return the created scan in failed state instead of leaving it queued.

| Setting | Default | Purpose |
| --- | --- | --- |
| `SCAN_HEARTBEAT_INTERVAL_SECONDS` | `30` | Worker heartbeat and API recovery interval |
| `SCAN_STALE_AFTER_SECONDS` | `300` | Heartbeat age before interruption recovery; must exceed twice the heartbeat interval |
| `SCAN_RECOVERY_BATCH_SIZE` | `100` | Maximum stale recoveries per pass and queued resubmissions at startup; range 1–1000 |

Recovery starts in the API background after database initialisation. Startup resubmits at most
one batch of queued scans in Celery mode. Keep the API running for periodic recovery. Eager
mode still executes scans synchronously. Stop old API/worker processes before applying the
new migrations. Recovery prevents stale result writes, but does not forcibly stop scanner
processes or guarantee exactly-once delivery of external SCM notifications.

## Docker (Cross-Platform Local Repo Scans)

For `file://` scan targets, mount a host repo root into the containers:

```bash
VIGILWEAVE_HOST_REPO_ROOT=/absolute/path/on/host \
VIGILWEAVE_CONTAINER_REPO_ROOT=/workspace \
API_HOST_PORT=8002 \
FRONTEND_HOST_PORT=8081 \
VITE_API_BASE_URL=http://localhost:8002 \
docker compose up -d --build
```

For a SaaS-style runtime with WorkOS authentication:

```bash
SESSION_AUTH_PROVIDER=workos \
API_KEYS_ENABLED=true \
SAAS_ENABLED=true \
WORKOS_API_KEY=YOUR_WORKOS_API_KEY_HERE \
WORKOS_CLIENT_ID=YOUR_WORKOS_CLIENT_ID_HERE \
SESSION_SECRET="$(openssl rand -hex 32)" \
docker compose -f docker-compose.yml -f docker-compose.enterprise.yml up -d --build
```

## Tests

Documentation uses `YOUR_..._HERE` placeholders, and example contact addresses use the
reserved `example.com` domain. These values are illustrative, not usable credentials or
monitored inboxes. Replace placeholders locally and never commit the resulting credentials.
Automated tests retain synthetic passwords, tokens, and licence keys to exercise authentication
and parsing; those fixtures are not deployment credentials.

```bash
source .venv/bin/activate
pytest -m "not e2e"
./scripts/run_e2e_tests.sh
```

## API Contract

Core endpoints:

- `POST /api/v1/scans/` : Start a scan
- `GET /api/v1/scans/{scan_id}` : Scan status and metadata
- `GET /api/v1/scans/{scan_id}/findings` : Findings list
- `GET /api/v1/scans/{scan_id}/sarif` : SARIF export
- `GET /api/v1/projects/` : Project management
- `GET /api/v1/system/capabilities` : License and feature flags

Full API reference: `docs/openapi.json`

Provider integration details: [SCM providers](docs/scm-providers-api.md).

## Scanner Matrix

| Scanner | Coverage |
|---------|----------|
| Semgrep | Multi-language SAST |
| Bandit | Python security |
| Ruff | Python quality/complexity |
| Checkov | IaC policy (Terraform, K8s, Dockerfile) |
| TFLint | Terraform-native linting |
| cfn-lint | CloudFormation validation |
| Trivy | Container/dependency CVEs |
| Gitleaks | Secrets detection |
| SQLFluff | SQL linting |
| SwiftLint | iOS/Swift |
| Detekt | Kotlin |
| Roslyn | .NET/C# |
| ESLint | JavaScript/TypeScript |

## ARM64 Containers

- `docker-bake.hcl` targets `linux/arm64`
- `scripts/build_multiarch_images.sh` runs `docker buildx bake`
- The enterprise image group adds Java, Detekt, SwiftLint, Android SDK, and .NET SDK

## Pipeline Assets

- GitHub Actions: `.github/workflows/ci-cd.yml`
- Azure Pipelines: `azure-pipelines.yml`, `azure-pipelines-examples/`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Do not include credentials, personal data, or
unpatched security vulnerabilities in public issues.

## License

[MIT](LICENSE).
