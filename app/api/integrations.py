"""External integration endpoints."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.core.licensing import Feature, require_feature
from app.core.network_security import sanitize_url
from app.core.security import require_scope
from app.core.workos_session import (
    SessionCookieError,
    decode_workos_cookie,
    encode_workos_cookie,
)
from app.models import (
    AzureMarketplaceOnboardRequest,
    AzureMarketplaceOnboardResponse,
    GitHubAppInstallationPublic,
    GitHubAppInstallationReassignRequest,
    GitHubAppInstallationReassignResponse,
    GitHubAppInstallLink,
    GitHubAppLinkedRepoPublic,
    IntegrationsSetupResponse,
    PrismaImportRequest,
    PrismaImportResponse,
    PrismaSyncRequest,
    PrismaSyncResponse,
    Project,
    ProjectRepository,
    SCMConnection,
    SCMProvider,
    SCMRepository,
    SonarRulesImportRequest,
    SonarRulesImportResponse,
    SonarRulesListResponse,
    SonarRulesSyncRequest,
    SonarRulesSyncResponse,
    TenantGitHubInstallation,
)
from app.services.azure_marketplace import onboard_azure_project
from app.services.github_app import (
    get_installation,
    github_app_configured,
    github_app_install_url,
    list_installation_repositories,
)
from app.services.policy_engine import write_audit_event
from app.services.prisma import import_prisma_findings, sync_prisma_findings
from app.services.sonarqube import (
    import_sonarqube_rules,
    load_sonarqube_rule_pack,
    sync_sonarqube_rules,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _public_webhook_url(path: str) -> str:
    base_url = settings.vigilweave_api_base_url.rstrip("/")
    api_prefix = settings.api_v1_prefix.rstrip("/")
    return f"{base_url}{api_prefix}{path}"


def _public_setup_url(path: str) -> str:
    return _public_webhook_url(path)


def _normalize_github_return_to(return_to: str | None) -> str:
    default_path = "/onboarding"
    if not return_to:
        return default_path

    parsed = urlsplit(return_to)
    if parsed.scheme or parsed.netloc:
        return default_path

    path = parsed.path or default_path
    if path not in {"/onboarding", "/projects", "/integrations"} and not path.startswith(
        "/projects/"
    ):
        return default_path

    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in {"githubAppConnected", "githubAppMessage"}
    ]
    return urlunsplit(("", "", path, urlencode(filtered_query), ""))


def _github_install_redirect_url(
    *, success: bool, detail: str | None = None, return_to: str | None = None
) -> str:
    normalized_return_to = _normalize_github_return_to(return_to)
    parsed = urlsplit(normalized_return_to)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if parsed.path == "/onboarding":
        params.setdefault("repoMode", "github_app")
    params["githubAppConnected"] = "1" if success else "0"
    if detail:
        params["githubAppMessage"] = detail
    redirect_target = urlunsplit(("", "", parsed.path, urlencode(params), ""))
    return f"{settings.vigilweave_web_base_url.rstrip('/')}{redirect_target}"


def _decode_github_install_state(state: str) -> dict[str, str]:
    try:
        raw_payload = decode_workos_cookie("github-app-install", state)
    except SessionCookieError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid install state"
        ) from exc

    if not raw_payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing install state")

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid install state"
        ) from exc

    tenant_slug = payload.get("tenant_slug")
    if not isinstance(tenant_slug, str) or not tenant_slug:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid install state")

    return_to = payload.get("return_to")
    normalized_return_to = return_to if isinstance(return_to, str) else None
    return {
        "tenant_slug": tenant_slug,
        "return_to": _normalize_github_return_to(normalized_return_to),
    }


def _serialize_installation(
    session: Session,
    *,
    tenant_slug: str,
    installation: TenantGitHubInstallation,
) -> GitHubAppInstallationPublic:
    linked_repo_count = session.exec(
        select(func.count())
        .select_from(ProjectRepository)
        .join(Project, Project.id == ProjectRepository.project_id)
        .where(
            Project.tenant_slug == tenant_slug,
            ProjectRepository.github_installation_id == installation.installation_id,
        )
    ).one()
    return GitHubAppInstallationPublic(
        installation_id=installation.installation_id,
        account_login=installation.account_login,
        account_type=installation.account_type,
        account_avatar_url=installation.account_avatar_url,
        linked_repo_count=linked_repo_count,
        created_at=installation.created_at,
        updated_at=installation.updated_at,
    )


def _get_tenant_installation(
    session: Session, *, tenant_slug: str, installation_id: int
) -> TenantGitHubInstallation | None:
    return session.exec(
        select(TenantGitHubInstallation).where(
            TenantGitHubInstallation.tenant_slug == tenant_slug,
            TenantGitHubInstallation.installation_id == installation_id,
        )
    ).first()


def _linked_project_repos_for_installation(
    session: Session, *, tenant_slug: str, installation_id: int
) -> list[tuple[ProjectRepository, Project]]:
    return session.exec(
        select(ProjectRepository, Project)
        .join(Project, Project.id == ProjectRepository.project_id)
        .where(
            Project.tenant_slug == tenant_slug,
            ProjectRepository.github_installation_id == installation_id,
        )
        .order_by(Project.key.asc(), ProjectRepository.repo.asc())
    ).all()


def _validate_reassignment_target(
    session: Session,
    *,
    tenant_slug: str,
    source_installation_id: int,
    payload: GitHubAppInstallationReassignRequest,
) -> None:
    if (
        payload.target_scm_connection_id is None and payload.target_github_installation_id is None
    ) or (
        payload.target_scm_connection_id is not None
        and payload.target_github_installation_id is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select either an SCM connection or another GitHub App installation",
        )

    if payload.target_scm_connection_id is not None:
        connection = session.exec(
            select(SCMConnection).where(
                SCMConnection.id == payload.target_scm_connection_id,
                SCMConnection.tenant_slug == tenant_slug,
            )
        ).first()
        if connection is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SCM connection not found for this tenant",
            )
        if connection.provider != SCMProvider.GITHUB:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Linked GitHub repositories can only be reassigned to a GitHub SCM connection"
                ),
            )
        if not connection.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected SCM connection is inactive",
            )

    if payload.target_github_installation_id is not None:
        if payload.target_github_installation_id == source_installation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Select a different GitHub App installation",
            )

        installation = _get_tenant_installation(
            session,
            tenant_slug=tenant_slug,
            installation_id=payload.target_github_installation_id,
        )
        if installation is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub App installation not found for this tenant",
            )


@router.get("/setup", response_model=IntegrationsSetupResponse)
def get_integrations_setup(
    principal=Depends(require_scope("scan:read")),
) -> IntegrationsSetupResponse:
    """Return guided setup status for first-party integrations."""

    github_webhook_url = _public_webhook_url("/webhooks/github")
    azure_webhook_url = _public_webhook_url("/webhooks/azure-devops")
    github_missing: list[str] = []
    if not settings.github_app_id:
        github_missing.append("GitHub App ID")
    if not settings.github_app_private_key:
        github_missing.append("GitHub App private key")
    if not settings.github_webhook_secret:
        github_missing.append("GitHub webhook secret")
    if not settings.github_app_slug:
        github_missing.append("GitHub App slug")

    install_url = (
        f"https://github.com/apps/{settings.github_app_slug}/installations/new"
        if settings.github_app_slug
        else None
    )
    setup_url = _public_setup_url("/integrations/github-app/callback")

    return IntegrationsSetupResponse(
        github={
            "configured": github_app_configured() and bool(settings.github_webhook_secret),
            "app_id_configured": bool(settings.github_app_id),
            "private_key_configured": bool(settings.github_app_private_key),
            "webhook_secret_configured": bool(settings.github_webhook_secret),
            "app_slug": settings.github_app_slug,
            "install_url": install_url,
            "setup_url": setup_url,
            "webhook_url": github_webhook_url,
            "tenant_slug": principal.tenant_slug,
            "default_scan_type": settings.github_default_scan_type,
            "check_name": settings.github_check_name,
            "missing_requirements": github_missing,
        },
        azure_devops={
            "onboarding_enabled": settings.azure_marketplace_onboarding_enabled,
            "webhook_secret_configured": bool(settings.azure_webhook_secret),
            "webhook_url": azure_webhook_url,
            "tenant_slug": principal.tenant_slug,
            "default_scan_type": settings.azure_default_scan_type,
            "default_events": [
                "git.pullrequest.created",
                "git.pullrequest.updated",
            ],
        },
    )


@router.get("/github-app/install-url", response_model=GitHubAppInstallLink)
def get_github_app_install_url(
    return_to: str | None = None,
    principal=Depends(require_scope("admin")),
) -> GitHubAppInstallLink:
    """Return a tenant-bound GitHub App installation URL."""

    state = encode_workos_cookie(
        "github-app-install",
        json.dumps(
            {
                "tenant_slug": principal.tenant_slug,
                "issued_at": datetime.now(UTC).isoformat(),
                "return_to": _normalize_github_return_to(return_to),
            }
        ),
    )
    install_url = github_app_install_url(state)
    if install_url is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub App onboarding is not configured",
        )
    return GitHubAppInstallLink(install_url=install_url)


@router.get("/github-app/callback")
def github_app_callback(
    installation_id: int | None = None,
    state: str | None = None,
    setup_action: str | None = None,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Handle GitHub App setup redirects and bind installations to tenants."""

    del setup_action
    if installation_id is None or not state:
        return RedirectResponse(
            url=_github_install_redirect_url(
                success=False,
                detail="GitHub App installation failed.",
            ),
        )

    try:
        install_state = _decode_github_install_state(state)
    except HTTPException:
        return RedirectResponse(
            url=_github_install_redirect_url(
                success=False,
                detail="GitHub App state validation failed.",
            ),
        )

    installation = get_installation(installation_id)
    if installation is None:
        return RedirectResponse(
            url=_github_install_redirect_url(
                success=False,
                detail="GitHub App installation could not be verified.",
                return_to=install_state.get("return_to"),
            ),
        )

    account = installation.get("account") or {}
    account_login = str(account.get("login") or "").strip()
    if not account_login:
        return RedirectResponse(
            url=_github_install_redirect_url(
                success=False,
                detail="GitHub App installation is missing account details.",
                return_to=install_state.get("return_to"),
            ),
        )

    record = session.exec(
        select(TenantGitHubInstallation).where(
            TenantGitHubInstallation.installation_id == installation_id,
        )
    ).first()
    if record is None:
        record = TenantGitHubInstallation(
            tenant_slug=install_state["tenant_slug"],
            installation_id=installation_id,
            account_login=account_login,
            account_type=account.get("type"),
            account_avatar_url=account.get("avatar_url"),
        )
    else:
        if record.tenant_slug != install_state["tenant_slug"]:
            return RedirectResponse(
                url=_github_install_redirect_url(
                    success=False,
                    detail="GitHub App installation is already linked to another tenant.",
                    return_to=install_state.get("return_to"),
                ),
            )
        record.tenant_slug = install_state["tenant_slug"]
        record.account_login = account_login
        record.account_type = account.get("type")
        record.account_avatar_url = account.get("avatar_url")
        record.updated_at = datetime.now(UTC)
    session.add(record)
    session.commit()

    return RedirectResponse(
        url=_github_install_redirect_url(
            success=True,
            detail=f"GitHub App connected for {account_login}.",
            return_to=install_state.get("return_to"),
        )
    )


@router.get(
    "/github-app/installations",
    response_model=list[GitHubAppInstallationPublic],
)
def list_github_app_installations(
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> list[GitHubAppInstallationPublic]:
    """List GitHub App installations mapped to the current tenant."""

    installations = session.exec(
        select(TenantGitHubInstallation)
        .where(TenantGitHubInstallation.tenant_slug == principal.tenant_slug)
        .order_by(TenantGitHubInstallation.account_login.asc())
    ).all()
    return [
        _serialize_installation(
            session, tenant_slug=principal.tenant_slug, installation=installation
        )
        for installation in installations
    ]


@router.delete(
    "/github-app/installations/{installation_id}",
    response_model=GitHubAppInstallationPublic,
)
def delete_github_app_installation(
    installation_id: int,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> GitHubAppInstallationPublic:
    """Unlink a tenant's GitHub App installation from VigilWeave."""

    installation = _get_tenant_installation(
        session,
        tenant_slug=principal.tenant_slug,
        installation_id=installation_id,
    )
    if installation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub App installation not found",
        )

    serialized = _serialize_installation(
        session,
        tenant_slug=principal.tenant_slug,
        installation=installation,
    )
    if serialized.linked_repo_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "GitHub App installation is still linked to "
                f"{serialized.linked_repo_count} project repositor"
                f"{'y' if serialized.linked_repo_count == 1 else 'ies'}. "
                "Reassign or remove those repositories first."
            ),
        )

    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="integration.github_app.unlink",
        entity_type="github_installation",
        entity_id=str(installation.installation_id),
        details={"account_login": installation.account_login},
    )
    session.delete(installation)
    session.commit()
    return serialized


@router.get(
    "/github-app/installations/{installation_id}/linked-repos",
    response_model=list[GitHubAppLinkedRepoPublic],
)
def list_github_app_installation_linked_repos(
    installation_id: int,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> list[GitHubAppLinkedRepoPublic]:
    """List project repos currently bound to a tenant GitHub App installation."""

    installation = _get_tenant_installation(
        session,
        tenant_slug=principal.tenant_slug,
        installation_id=installation_id,
    )
    if installation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub App installation not found",
        )

    return [
        GitHubAppLinkedRepoPublic(
            project_key=project.key,
            project_name=project.name,
            repo=repo_link.repo,
        )
        for repo_link, project in _linked_project_repos_for_installation(
            session,
            tenant_slug=principal.tenant_slug,
            installation_id=installation_id,
        )
    ]


@router.post(
    "/github-app/installations/{installation_id}/reassign",
    response_model=GitHubAppInstallationReassignResponse,
)
def reassign_github_app_installation_repos(
    installation_id: int,
    payload: GitHubAppInstallationReassignRequest,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> GitHubAppInstallationReassignResponse:
    """Bulk reassign project repos linked to a tenant GitHub App installation."""

    installation = _get_tenant_installation(
        session,
        tenant_slug=principal.tenant_slug,
        installation_id=installation_id,
    )
    if installation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub App installation not found",
        )

    _validate_reassignment_target(
        session,
        tenant_slug=principal.tenant_slug,
        source_installation_id=installation_id,
        payload=payload,
    )

    linked_repos = _linked_project_repos_for_installation(
        session,
        tenant_slug=principal.tenant_slug,
        installation_id=installation_id,
    )
    reassigned_count = 0
    for repo_link, _project in linked_repos:
        repo_link.github_installation_id = payload.target_github_installation_id
        repo_link.scm_connection_id = payload.target_scm_connection_id
        session.add(repo_link)
        reassigned_count += 1

    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="integration.github_app.reassign",
        entity_type="github_installation",
        entity_id=str(installation.installation_id),
        details={
            "account_login": installation.account_login,
            "reassigned_count": reassigned_count,
            "target_scm_connection_id": payload.target_scm_connection_id,
            "target_github_installation_id": payload.target_github_installation_id,
        },
    )
    session.commit()
    return GitHubAppInstallationReassignResponse(reassigned_count=reassigned_count)


@router.get(
    "/github-app/installations/{installation_id}/repositories",
    response_model=list[SCMRepository],
)
def list_github_app_installation_repositories(
    installation_id: int,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> list[SCMRepository]:
    """List repositories visible to a tenant's GitHub App installation."""

    installation = session.exec(
        select(TenantGitHubInstallation).where(
            TenantGitHubInstallation.tenant_slug == principal.tenant_slug,
            TenantGitHubInstallation.installation_id == installation_id,
        )
    ).first()
    if installation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="GitHub App installation not found",
        )

    return list_installation_repositories(installation_id)


@router.post(
    "/prisma/import",
    response_model=PrismaImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def prisma_import(
    payload: PrismaImportRequest,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:write")),
    _: object = Depends(require_feature(Feature.CUSTOM_ADAPTERS)),
) -> PrismaImportResponse:
    """Import normalized Prisma findings into VigilWeave."""

    scan = import_prisma_findings(
        session, payload, tenant_slug=principal.tenant_slug, actor=principal.actor
    )
    write_audit_event(
        session,
        tenant_slug=scan.tenant_slug,
        actor=principal.actor,
        action="integration.prisma.import",
        entity_type="scan",
        entity_id=str(scan.id),
        details={"repo": scan.repo, "findings_imported": len(payload.findings)},
    )
    session.commit()
    return PrismaImportResponse(scan=scan, findings_imported=len(payload.findings))


@router.post(
    "/prisma/sync",
    response_model=PrismaSyncResponse,
    status_code=status.HTTP_201_CREATED,
)
def prisma_sync(
    payload: PrismaSyncRequest,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:write")),
    _: object = Depends(require_feature(Feature.CUSTOM_ADAPTERS)),
) -> PrismaSyncResponse:
    """Fetch and import Prisma findings from a remote endpoint."""

    try:
        scan = sync_prisma_findings(
            session, payload, tenant_slug=principal.tenant_slug, actor=principal.actor
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    safe_source_url = sanitize_url(payload.api_url)
    write_audit_event(
        session,
        tenant_slug=scan.tenant_slug,
        actor=principal.actor,
        action="integration.prisma.sync",
        entity_type="scan",
        entity_id=str(scan.id),
        details={"repo": scan.repo, "source_url": safe_source_url},
    )
    session.commit()
    findings_imported = scan.total_findings + scan.suppressed_findings
    return PrismaSyncResponse(
        scan=scan, findings_imported=findings_imported, source_url=safe_source_url
    )


@router.post(
    "/sonarqube/rules/import",
    response_model=SonarRulesImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def sonarqube_rules_import(
    payload: SonarRulesImportRequest,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:write")),
    _: object = Depends(require_feature(Feature.CUSTOM_ADAPTERS)),
) -> SonarRulesImportResponse:
    """Import SonarQube rules and convert them into VigilWeave rule definitions."""

    response = import_sonarqube_rules(payload, tenant_slug=principal.tenant_slug)
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="integration.sonarqube.rules.import",
        entity_type="ruleset",
        entity_id=payload.language,
        details={
            "language": response.language,
            "rules_imported": response.rules_imported,
            "persisted_path": response.persisted_path,
        },
    )
    session.commit()
    return response


@router.post(
    "/sonarqube/rules/sync",
    response_model=SonarRulesSyncResponse,
    status_code=status.HTTP_201_CREATED,
)
def sonarqube_rules_sync(
    payload: SonarRulesSyncRequest,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:write")),
    _: object = Depends(require_feature(Feature.CUSTOM_ADAPTERS)),
) -> SonarRulesSyncResponse:
    """Fetch SonarQube rules from a remote SonarQube API and convert them."""

    try:
        response = sync_sonarqube_rules(payload, tenant_slug=principal.tenant_slug)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    safe_source_url = sanitize_url(response.source_url)
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="integration.sonarqube.rules.sync",
        entity_type="ruleset",
        entity_id=response.language,
        details={
            "language": response.language,
            "source_url": safe_source_url,
            "rules_imported": response.rules_imported,
            "persisted_path": response.persisted_path,
        },
    )
    session.commit()
    return SonarRulesSyncResponse(
        **response.model_dump(exclude={"source_url"}),
        source_url=safe_source_url,
    )


@router.get("/sonarqube/rules/{language}", response_model=SonarRulesListResponse)
def sonarqube_rules_get(
    language: str,
    principal=Depends(require_scope("scan:read")),
) -> SonarRulesListResponse:
    """Return persisted SonarQube-derived rules for the requested language."""

    response = load_sonarqube_rule_pack(principal.tenant_slug, language)
    if response is None:
        return SonarRulesListResponse(language=language, rules=[])
    return response


@router.post(
    "/azure-devops/onboard-project",
    response_model=AzureMarketplaceOnboardResponse,
    status_code=status.HTTP_201_CREATED,
)
def azure_onboard_project(
    payload: AzureMarketplaceOnboardRequest,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
    _: object = Depends(require_feature(Feature.CUSTOM_ADAPTERS)),
) -> AzureMarketplaceOnboardResponse:
    """Create Azure DevOps service-hook subscriptions for a selected project."""

    try:
        response = onboard_azure_project(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    safe_org_url = sanitize_url(payload.organization_url)
    write_audit_event(
        session,
        tenant_slug=principal.tenant_slug,
        actor=principal.actor,
        action="integration.azure.onboard",
        entity_type="project",
        entity_id=payload.project,
        details={
            "organization_url": safe_org_url,
            "subscriptions_created": response.subscriptions_created,
            "events": payload.events,
        },
    )
    session.commit()
    return response
