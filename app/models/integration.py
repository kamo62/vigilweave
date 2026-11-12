"""Integration models for Prisma Cloud import and sync."""

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Field, SQLModel

from app.models.finding import FindingPublic
from app.models.scan import ScanPublic


class PrismaFindingPayload(SQLModel):
    """Normalized Prisma finding payload accepted by import flows."""

    severity: str
    title: str
    message: str
    description: str | None = None
    category: str = "security"
    tool: str = "prisma-cloud"
    file_path: str | None = None
    line: int | None = None
    column: int | None = None
    rule_id: str | None = None
    fingerprint: str | None = None
    cwe_id: str | None = None
    owasp_category: str | None = None
    confidence: str | None = None
    raw: dict[str, Any] | None = None


class PrismaImportRequest(SQLModel):
    """Manual Prisma import payload."""

    repo: str
    branch: str | None = None
    commit: str | None = None
    findings: list[PrismaFindingPayload]
    integration_metadata: dict[str, Any] = Field(default_factory=dict)


class PrismaImportResponse(SQLModel):
    """Prisma import result."""

    scan: ScanPublic
    findings_imported: int


class PrismaSyncRequest(SQLModel):
    """Remote Prisma sync request."""

    api_url: str
    repo: str
    branch: str | None = None
    commit: str | None = None
    access_key: str | None = None
    access_secret: str | None = None
    auth_headers: dict[str, str] = Field(default_factory=dict)
    results_path: str | None = None
    integration_metadata: dict[str, Any] = Field(default_factory=dict)


class PrismaSyncResponse(SQLModel):
    """Prisma sync result."""

    scan: ScanPublic
    findings_imported: int
    source_url: str


class ImportedFindingsPreview(SQLModel):
    """Simple preview response used by integrations and IDE tooling."""

    findings: list[FindingPublic]
    severities: dict[str, int] = Field(default_factory=dict)


class SonarRulePayload(SQLModel):
    """Raw SonarQube rule shape used for import and conversion."""

    key: str
    name: str
    lang: str | None = None
    repo: str | None = None
    severity: str | None = None
    type: str | None = None
    status: str | None = None
    htmlDesc: str | None = None
    mdDesc: str | None = None
    cleanCodeAttribute: str | None = None
    tags: list[str] = Field(default_factory=list)
    sysTags: list[str] = Field(default_factory=list)
    params: list[dict[str, Any]] = Field(default_factory=list)
    impacts: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class VigilWeaveRuleDefinition(SQLModel):
    """Normalized VigilWeave rule derived from external rule catalogs."""

    vigilweave_rule_id: str
    source: str = "sonarqube"
    source_rule_key: str
    source_repository: str | None = None
    language: str
    title: str
    description: str | None = None
    severity: str
    category: str
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True


class SonarRulesImportRequest(SQLModel):
    """Manual SonarQube rule import payload."""

    language: str
    rules: list[SonarRulePayload]
    profile_name: str | None = None
    persist: bool = True


class SonarRulesImportResponse(SQLModel):
    """Result for SonarQube rule import and conversion."""

    language: str
    profile_name: str | None = None
    rules_imported: int
    rules: list[VigilWeaveRuleDefinition]
    persisted_path: str | None = None


class SonarRulesSyncRequest(SQLModel):
    """Fetch SonarQube rules from a remote SonarQube instance and convert them."""

    base_url: str
    token: str
    language: str
    quality_profile: str | None = None
    profile_name: str | None = None
    include_inactive: bool = False
    auth_scheme: str = "bearer"
    page_size: int = Field(default=500, ge=1, le=500)
    persist: bool = True


class SonarRulesSyncResponse(SonarRulesImportResponse):
    """Result for remote SonarQube rule sync."""

    source_url: str


class SonarRulesListResponse(SQLModel):
    """Persisted SonarQube-derived rules for a language."""

    language: str
    profile_name: str | None = None
    rules: list[VigilWeaveRuleDefinition]
    persisted_path: str | None = None
    updated_at: datetime | None = None


class GitHubWebhookResponse(SQLModel):
    """GitHub webhook ingestion result."""

    accepted: bool
    event: str
    action: str | None = None
    message: str
    scan_id: int | None = None
    check_run_id: int | None = None


class AzureWebhookResponse(SQLModel):
    """Azure DevOps service-hook ingestion result."""

    accepted: bool
    event: str
    message: str
    scan_id: int | None = None


class AzureMarketplaceOnboardRequest(SQLModel):
    """Request payload for Azure Marketplace onboarding automation."""

    organization_url: str
    project: str
    access_token: str
    auth_scheme: str = "bearer"
    webhook_url: str
    events: list[str] = Field(
        default_factory=lambda: ["git.pullrequest.created", "git.pullrequest.updated"]
    )
    repository: str | None = None
    branch: str | None = None
    secret: str | None = None
    detailed_messages_to_send: bool = True


class AzureMarketplaceOnboardResponse(SQLModel):
    """Azure Marketplace onboarding response."""

    project: str
    subscriptions_created: int
    subscriptions: list[dict[str, Any]] = Field(default_factory=list)


class GitHubIntegrationSetup(SQLModel):
    """GitHub App setup status for the current deployment."""

    configured: bool
    app_id_configured: bool
    private_key_configured: bool
    webhook_secret_configured: bool
    app_slug: str | None = None
    install_url: str | None = None
    setup_url: str | None = None
    webhook_url: str
    tenant_slug: str
    default_scan_type: str
    check_name: str
    missing_requirements: list[str] = Field(default_factory=list)


class TenantGitHubInstallation(SQLModel, table=True):
    """Tenant-scoped mapping to a GitHub App installation."""

    __tablename__ = "tenant_github_installations"

    id: int | None = Field(default=None, primary_key=True)
    tenant_slug: str = Field(index=True)
    installation_id: int = Field(index=True, unique=True)
    account_login: str
    account_type: str | None = None
    account_avatar_url: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GitHubAppInstallationPublic(SQLModel):
    """GitHub App installation visible to a tenant admin."""

    installation_id: int
    account_login: str
    account_type: str | None = None
    account_avatar_url: str | None = None
    linked_repo_count: int = 0
    created_at: datetime
    updated_at: datetime


class GitHubAppLinkedRepoPublic(SQLModel):
    """Project repository currently bound to a tenant GitHub App installation."""

    project_key: str
    project_name: str
    repo: str


class GitHubAppInstallationReassignRequest(SQLModel):
    """Bulk reassignment target for repos linked to a GitHub App installation."""

    target_scm_connection_id: int | None = None
    target_github_installation_id: int | None = None


class GitHubAppInstallationReassignResponse(SQLModel):
    """Bulk reassignment result for a tenant GitHub App installation."""

    reassigned_count: int


class GitHubAppInstallLink(SQLModel):
    """Install URL payload for GitHub App onboarding."""

    install_url: str


class AzureDevOpsIntegrationSetup(SQLModel):
    """Azure DevOps webhook/onboarding status for the current deployment."""

    onboarding_enabled: bool
    webhook_secret_configured: bool
    webhook_url: str
    tenant_slug: str
    default_scan_type: str
    default_events: list[str] = Field(default_factory=list)


class IntegrationsSetupResponse(SQLModel):
    """Setup status for supported first-party integrations."""

    github: GitHubIntegrationSetup
    azure_devops: AzureDevOpsIntegrationSetup
