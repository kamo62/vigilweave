# VigilWeave

This is an educational test application for understanding how code-quality and security
analysis tools such as SonarQube work. Use it to explore scanning, findings, quality gates,
and reporting in a controlled local environment.

It is not a production-ready service or an official SonarQube project. Use synthetic data
and disposable test credentials only. Do not connect production systems or upload customer
data. The edition controls are retained for testing, not as a commercial offering from this
repository.

The application scans repositories for
security vulnerabilities, secret leaks, dependency risks, infrastructure-as-code misconfiguration,
and code quality issues, then presents the results through a web dashboard, a REST API, CI/CD
integrations, IDE extensions, and an MCP server.

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

## Worker

```bash
source .venv/bin/activate
celery -A app.core.celery_app.celery_app worker --loglevel=info
```

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
WORKOS_API_KEY=sk_... \
WORKOS_CLIENT_ID=client_... \
SESSION_SECRET="$(openssl rand -hex 32)" \
docker compose -f docker-compose.yml -f docker-compose.enterprise.yml up -d --build
```

## Tests

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

See [CONTRIBUTING.md](CONTRIBUTING.md). Security issues should be reported privately to
security@vigilweave.com rather than through public issues.

## License

[MIT](LICENSE).
