# VigilWeave — Changelog

Implementation updates for VigilWeave. For setup, see [README.md](../README.md).

---

## 2026-11-12: Public educational test application

- Documented VigilWeave's educational purpose for learning how tools such as SonarQube work.
- Removed commercial funding links.
- Retained the MIT licence and the existing application behaviour.

## 2026-03-24 — Production Readiness Pass, Explicit Scan Assignment & License Operations Console

- **Explicit scan-to-project assignment**: Added `project_id`, `project_key`, and `assignment_status` to scans. `POST /api/v1/scans/` now accepts an optional `project_key`; scans submitted without it remain intentionally `unassigned` instead of being inferred from repo-string matching. Project dashboards now read explicit scan ownership rather than repository URL coincidence.
- **Private-repo scan linkage cleanup**: SCM-linked scans now resolve credentials through tenant-scoped project repository mappings. Imported repositories retain `scm_connection_id`, and later scans copy that mapping into scan metadata only when the repo is actually attached to the selected project.
- **Webhook routing hardening**: GitHub and Azure DevOps ingestion now routes through persisted project/integration mappings instead of deployment-global tenant defaults. Added delivery-id persistence and replay suppression for webhook processing.
- **Runtime hardening**: Added `/ready` with DB/Redis/session-secret checks, request-size limits for mutating requests, and production secret validation for session/offline-license paths. Rate limiting now uses Redis outside development/test and is applied to auth, export, and webhook endpoints.
- **License verification cache hardening**: Main-app online license verification now uses database-backed cache records for normal runtime behavior rather than depending on a shared filesystem cache file.
- **License server operator control plane**: Replaced the old shared-admin-key utility flow with a real operator console. The license server now supports local bootstrap, session-backed login/logout, admin/viewer roles, operator management, audit logs, paginated key inventory, verification history, CSV export, revoke/reactivate/reissue/bulk actions, and same-origin console serving.
- **Enterprise directory auth for license operations**: Added optional LDAP / Active Directory login for the license server with encrypted bind credentials, group-to-role mapping, connection testing, and break-glass local admin support.
- **Production license-server posture**: Production startup now requires `SESSION_SECRET`, `CONFIG_ENCRYPTION_KEY`, and `OFFLINE_SIGNING_SECRET`; PostgreSQL is the intended production datastore, while SQLite remains a local-development fallback.

## 2026-03-24 — Production Security Hardening (Phase 2: CSRF + Verification)

- **CSRF protection for browser-session mutations**: Added double-submit CSRF defenses for cookie-auth mutation routes via new `GET /api/v1/auth/csrf` token issuance and `X-CSRF-Token` enforcement on local-auth and WorkOS mutation endpoints.
- **Selective enforcement for automation safety**: API-key automation calls remain compatible when no browser session cookie is present; CSRF is enforced when session cookies are used so browser-authenticated admin/user mutations are protected.
- **Global CSRF middleware for session mutations**: CSRF enforcement now runs centrally at the application middleware layer for all API mutation methods (`POST`/`PUT`/`PATCH`/`DELETE`) whenever a browser session cookie is present, instead of relying only on per-route coverage.
- **Frontend CSRF integration**: The SPA now fetches and stores CSRF tokens and attaches them to mutating requests (`POST`/`PATCH`/`PUT`/`DELETE`) with retry-on-403 token refresh behavior.
- **Auth surface coverage**: Applied CSRF checks to local setup/login/logout, WorkOS refresh/logout/profile update, and admin session-backed key/user mutations.
- **Regression tests expanded**: Added tests for CSRF token issuance, CSRF-required mutation failures, session-backed API-key mutation CSRF behavior, WorkOS profile update CSRF enforcement, and session-cookie CSRF enforcement on non-auth mutation routes (for example project creation).
- **Full backend suite verification**: Executed full backend test suite in a fresh virtual environment (`100 passed`).

## 2026-03-23 — Enterprise UI Refinement (Design System Polish)

- **Code block restyling**: Replaced all 42 `bg-slate-900 text-green-400` "hacker terminal" code blocks across 10 documentation pages with a theme-aware `.code-block` class using GitHub Light/Dark color tokens (`--code-bg`, `--code-fg`, `--code-command`, `--code-output`, `--code-highlight`, etc.). Code blocks now render as refined IDE-style output in both light and dark modes.
- **Light mode support**: Added `ThemeToggle` component (Sun/Moon toggle backed by `localStorage`). Removed hardcoded `class="dark"` from `index.html` and added a FOUC-prevention inline script that defaults to dark for first-time visitors. Toggle placed in both the authenticated sidebar (`Layout.tsx`) and the public header (`PublicLayout.tsx`).
- **Docs breadcrumbs & versioning**: Added `Docs > {Section}` breadcrumb navigation and a `v1.0.0-beta` version badge in the docs sidebar to signal product maturity.
- **Landing page terminal refinement**: Replaced green-on-black terminal colors with CSS variable references (`--code-command`, `--code-output`, `--code-highlight`). Renamed "terminal" label to "vigilweave CLI". Terminal card background now uses `var(--code-bg)`.
- **Brand gradient consolidation**: Replaced 10 hardcoded Tailwind arbitrary gradient values (`from-[#173bab] to-[#00288e]`) across `PublicLayout.tsx`, `LandingPage.tsx`, and `PricingPage.tsx` with centralized `.bg-brand-gradient` and `.text-brand-gradient` CSS utility classes.
- **PDF report brand alignment**: Updated `report_generator.py` embedded CSS to match the frontend palette — beige/green tokens replaced with slate/blue (`--bg: #f7f9fb`, `--accent: #1e40af`, etc.). Added Plus Jakarta Sans via Google Fonts link. Embedded VigilWeave logo SVG in the report header. Updated severity badge, code block, and gradient colors.
- **License server theming**: Replaced green-tinted palette in `services/license-server/frontend/` with blue/slate brand colors. Updated `index.css` (background, gradients, borders), `App.tsx` (all inline hardcoded colors), and added Plus Jakarta Sans font import.
- **Semantic color tokens**: Replaced raw Tailwind color classes (`text-green-400`, `text-emerald-500`) with design system tokens (`text-success`) in API reference badges and pricing checkmarks.

## 2026-03-23 — Admin User Management, MCP/Bulk Triage Docs, Domain-Aware Routing

- **Admin user management (backend + frontend)**: Added 3 new admin-only endpoints: `GET /auth/users` (list tenant users), `PATCH /auth/users/{id}/role` (change role with self-demotion guard), `DELETE /auth/users/{id}` (remove user with self-deletion guard). All write actions produce audit events. New `UsersTab` component in Settings with summary cards, user list (avatar, name, auth provider badge, join/last-login dates), role dropdown, and delete confirmation dialog.
- **MCP permissions documentation**: Expanded MCP integration docs with full 10-tool permissions table showing read vs write classification, descriptions, and required API key scopes. Documented that MCP inherits permissions from the API key — no separate permission model.
- **Bulk triage documentation**: Added comprehensive docs section covering the bulk triage workflow (select → filter → apply status), status definitions, Pro-tier gating, and REST API example for scripted bulk triage.
- **Auth docs update**: Added "Admin User Management" section to Auth & Users docs covering the Settings → Users tab, available actions (view/role-change/remove), audit trail, and API endpoints.

## 2026-03-23 — Production Security Hardening (Phase 1)

- **IDE analyze path traversal fix**: Hardened `POST /api/v1/ide/analyze` path handling to reject absolute paths and traversal (`..`) escapes before writing files into temporary workspaces. Invalid paths now return `422`.
- **Unsafe build-script adapters disabled by default**: `android-lint` and `dotnet-analyzers` now require explicit opt-in via `ENABLE_REPO_BUILD_TOOL_ADAPTERS=true`. This avoids executing repository-controlled build scripts by default in untrusted scans.
- **Credential redaction hardening**: Added centralized sanitization for URLs and error messages. Scan/tool failure metadata now redacts embedded credentials and token-like values before persistence and reporting.
- **Repository URL scheme restrictions**: Scan creation, repository blame, and webhook ingestion now reject unsupported repo schemes. Only `https://` and `file://` repository URLs are accepted.
- **Outbound integration URL safety**: Introduced shared outbound URL validation for Prisma, SonarQube, Azure DevOps onboarding, and HTTPS git clone targets to reduce SSRF risk (blocked localhost/private/non-routable targets).
- **Webhook abuse controls**: Added request size caps and webhook endpoint rate limiting (`429`/`413` paths) for GitHub and Azure DevOps webhook routes.
- **Migration safety hardening**: Database startup no longer auto-stamps Alembic head when `alembic_version` metadata is missing on a non-empty schema; startup now fails safe with remediation guidance.
- **Data integrity**: Added unique index migration for `(project_id, repo)` in `project_repositories` to prevent duplicate project-repository mappings.
- **Pagination guardrails**: Added configurable max limit for scan listing (`MAX_SCAN_LIST_LIMIT`, default `500`) and enforced bounds at API layer.
- **Tests**: Expanded regression coverage for IDE path traversal rejection, unsafe repository scheme rejection (scan/blame/webhooks), webhook payload limits, Sonar local URL rejection, capability hardening defaults, and build-tool adapter opt-in behavior.

## 2026-03-23 — Domain-Aware Routing, Enterprise Auth Docs & Remaining Cleanup

- **Domain-aware frontend routing**: Added `domain.ts` utility that detects whether the browser is on `vigilweave.com` (marketing) or `app.vigilweave.com` (application). The root route's `beforeLoad` hook redirects app routes (e.g. `/projects`) to `app.vigilweave.com` when accessed from the marketing domain, and vice versa. Self-hosted deployments remain unified — all routes served from a single origin. New env vars: `VITE_MARKETING_URL`, `VITE_APP_URL` (frontend build-time), `MARKETING_DOMAIN` (backend CORS).
- **Cross-domain nav links**: `PublicLayout` navbar and `LandingPage` CTA buttons are now domain-aware. On the marketing domain, "Log in", "Get Started", and "Dashboard" link to `app.vigilweave.com`. On the app domain, "Pricing" and "Docs" link to `vigilweave.com`. In unified mode (self-hosted), everything works as before.
- **Authentication & User Management docs**: New docs section covering all auth modes (local, WorkOS, API-key-only), enterprise SSO self-service setup (SAML/OIDC via WorkOS Admin Portal), directory sync (SCIM for AD/Okta/Azure AD), roles & permissions (admin/member), tenant isolation, and API key usage. Explicitly documents that enterprise admins configure SSO and directory sync self-service — no support ticket required.
- **Docker config**: Updated `frontend/Dockerfile` with `VITE_MARKETING_URL` and `VITE_APP_URL` build args. Updated `docker-compose.enterprise.yml` with `MARKETING_DOMAIN` env var and frontend build args. Updated `.env.example` with documentation for all new env vars.
- **LandingPage**: Fixed hero subtitle from "12+ security scanners" to capability-based language.

## 2026-03-22 — SCA Scanner, Domain Architecture, Docs Overhaul & Observability

- **SCA scanner (Grype)**: Added Software Composition Analysis via Grype as the 13th tool adapter. Covers Python, JavaScript, Go, Rust, Java, Kotlin, C#, Ruby, PHP. SARIF output parsed by existing `_parse_sarif()`. Dockerfile updated to install Grype + Syft binaries. Added `sca` category to `tools_config.yaml` and included it in the `comprehensive` scan type.
- **Domain architecture**: Formalized URL structure — `vigilweave.com` for the marketing site (landing, pricing, docs, downloads, legal) and `app.vigilweave.com` for the application (dashboard, API, authenticated services). Updated all WorkOS callback URIs, API base URL references, and cookie domain documentation accordingly.
- **Prometheus metrics endpoint**: Added `GET /api/v1/system/metrics/prometheus` returning metrics in Prometheus exposition format (`text/plain; version=0.0.4`) for scraping by Prometheus/Grafana. Exposes uptime, all counter metrics, and timer aggregates with proper label encoding.
- **Celery resource isolation**: Added `task_time_limit=1800` (hard kill at 30 min), `task_soft_time_limit=1500` (25 min), `worker_max_tasks_per_child=50`, and `worker_max_memory_per_child=2GB` to prevent runaway scans from starving workers.
- **SARIF branding**: Outbound SARIF export now identifies as `VigilWeave` with `informationUri: https://vigilweave.com` and `semanticVersion: 1.0.0`.
- **Tool name scrub**: Removed all OSS tool names (Semgrep, Bandit, Gitleaks, Trivy, etc.) from public-facing pages. All references replaced with capability names (SAST, Secrets, SCA, IaC). Internal `ScanDetailPage` maps tool IDs to user-facing labels via `ENGINE_LABELS`.
- **Docs overhaul**: Added deep-linking via `?section=` query parameter. Added search filtering. Created new documentation sections: Rules & Customization (SonarQube import, custom rule packs), SCM Connections, Webhooks. Fixed CI/CD integration examples to match actual GitHub Action and Azure DevOps Task inputs. Updated API Reference with interactive explorer links and correct `scan_type` usage.
- **Language detection**: Extended `SPECIAL_FILENAMES` in `language_detector.py` with 20+ package manifest filenames for improved SCA targeting.

## 2026-03-22 — SCM Connections & Design System

- **SCM Connections**: Added PAT-based connections to GitHub, GitLab, Bitbucket, and Azure DevOps for private repository scanning. Users can browse organizations, list repositories, and import them into projects. Tokens are Fernet-encrypted at rest using the `session_secret` key material.
- **Provider abstraction**: Implemented `SCMProviderClient` protocol with four implementations covering test connection, list organizations, list repositories, and authenticated clone URL generation. Each provider uses its official REST API (GitHub v2022-11-28, GitLab v4, Bitbucket v2.0, Azure DevOps v7.1).
- **Scanner integration**: `resolve_clone_url()` transparently injects authenticated clone URLs when a scan is linked to an SCM connection via `scan_metadata.scm_connection_id`. No changes to `git_utils.py` or downstream scanner logic.
- **API endpoints**: Full CRUD under `/api/v1/scm-connections` plus `POST /{id}/test`, `GET /{id}/organizations`, `GET /{id}/repositories`, and `POST /{id}/import-repos`. All admin-gated for write operations.
- **Database migration**: New `scm_connections` table and `scm_connection_id` FK on `project_repositories` to track which connection was used for each imported repo.
- **Frontend — Connections tab**: Added Settings → Connections tab with connection list (provider badge, status, masked token), add/test/delete actions, and provider-specific form fields (Bitbucket username, Azure DevOps organization).
- **Frontend — SCM import in Create Project**: Enhanced the Create Project dialog with Manual and Import from SCM tabs. Import tab provides connection picker → organization picker → repository browser with checkboxes.
- **Sentinel Core design system**: Aligned entire application to the Sentinel Core design system — Plus Jakarta Sans typography, `rounded-sm` (2px) everywhere, primary `#1E40AF`, gradient `from-[#173bab] to-[#00288e]`, sentinel shadow, no violet/indigo palette colors. Updated all shadcn/ui primitives (button, card, badge, dialog, select, input, textarea, tabs, tooltip, table), all page components, and both layout shells.
- **README**: Added "Local Dev with Full Features" section documenting `LICENSE_TESTING_MODE=true`, `SESSION_AUTH_PROVIDER=local`, `API_KEYS_ENABLED=true` for testing the full landing → setup → onboarding → projects flow locally.

## 2026-03-17 — Licensing System

- Implemented hybrid license verification system with four tiers: Community (free, offline), Pro (online verification, $69/dev/year), Enterprise Standard (online verification), and Enterprise Offline (self-verified, premium pricing for air-gapped deployments).
- Added `LICENSE_TESTING_MODE=true` environment variable to unlock all features for development without license keys.
- Implemented online license verification against `license.vigilweave.com` with 24-hour local caching and 7-day graceful fallback during outages.
- Implemented offline license validation for Enterprise Offline tier using HMAC-SHA256 signatures with 1-year validity from first use.
- Added comprehensive license verification tests (`tests/test_license_verification.py`) covering all four tiers, caching, expiration, and offline validation.
- Updated `.env.example` with license configuration options including testing mode and server settings.
- Created `docs/LICENSING_TESTING.md` with complete testing guide for developers.
- Added license tier usage metrics tracking (community/pro/enterprise) via `increment_metric()`.
- Updated OpenAPI spec (`docs/openapi.json`) with detailed license schema in CapabilityResponse, documenting all 15 features and their tier assignments.

## 2026-03-16 — V2 Governance, Reporting & Admin Surface

- Implemented V2 governance, reporting, and admin surface completion across backend, frontend, schema, and tests.
- Added `BULK_TRIAGE` and `CUSTOM_POLICIES` license features. Pro now gates bulk triage, custom policy CRUD, and extended audit access. Enterprise continues to gate advanced policy workflows and portfolios. Reporting/export endpoints are gated by `REPORTING`.
- Policies now support seeded tenant presets and custom policies. Added policy `kind` (`preset`, `custom`) and `preset_key` (`lenient`, `balanced`, `strict`), plus `PATCH /api/v1/policies/{policy_id}` and `DELETE /api/v1/policies/{policy_id}` for custom policies only.
- Preset policy defaults were implemented as: `lenient` critical `0`, high `10`, minimum quality `60`; `balanced` critical `0`, high `5`, minimum quality `70`; `strict` critical `0`, high `1`, minimum quality `80`.
- Policy UI now supports preset activation, Pro custom policy create/edit/delete, Enterprise-only waiver actions, and Pro-only audit visibility.
- Project detail now includes repository removal using the existing backend delete route.
- Portfolio management UI now supports create, edit, delete, parent portfolio selection, selection mode/value editing, and manual project membership management. Portfolio management remains an Enterprise-gated admin function.
- Tool governance UI now supports full tenant override management except scan-type editing: edit override metadata, create custom tool IDs, reset overrides for base tools, and delete tenant-defined custom tools.
- Added `GET /api/v1/integrations/setup` to expose GitHub and Azure DevOps setup state without requiring the frontend to infer configuration from environment variables.
- Integrations UI now prioritizes GitHub guided setup and Azure DevOps onboarding. Prisma and Sonar import flows remain available as secondary advanced tooling. GitLab onboarding was not added in this phase.
- GitHub onboarding is implemented as a guided setup/status flow, not automatic GitHub App registration. Azure DevOps onboarding now has a real frontend form around the existing onboarding API.
- Reporting v1 is implemented with `GET /api/v1/scans/{scan_id}/report/pdf` and `GET /api/v1/scans/{scan_id}/findings/export`. Export format for this phase is CSV only.
- PDF reporting is generated on demand from server-rendered HTML using Playwright/Chromium and is not persisted. Reports include scan metadata, gate verdict, severity/category/tool summaries, quality summary, and top findings with code context when available.
- Finding filter support was extended to `severity`, `category`, `tool`, `review_status`, and `include_suppressed`, and the same filter contract is now used by findings, PDF reporting, and CSV export.
- Tenant hardening was added to current aggregate paths so project and portfolio rollups respect tenant boundaries even when multiple tenants scan repositories with the same URL.
- Added regression coverage for tier gating, policy lifecycle behavior, reporting/export behavior, integration setup status, project/portfolio UI parity, and tenant-isolation rollups.
- SaaS-grade multi-tenancy remains explicitly deferred to V3. This phase does not add tenant provisioning, per-tenant memberships, billing, SSO tenant mapping, or PostgreSQL row-level security.
