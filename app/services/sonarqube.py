"""SonarQube rule import/sync and conversion helpers."""

from __future__ import annotations

import base64
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.core.network_security import ensure_safe_outbound_url
from app.models.integration import (
    SonarRulePayload,
    SonarRulesImportRequest,
    SonarRulesImportResponse,
    SonarRulesListResponse,
    SonarRulesSyncRequest,
    SonarRulesSyncResponse,
    VigilWeaveRuleDefinition,
)

LANGUAGE_ALIASES = {
    "py": "python",
    "python": "python",
    "js": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "kt": "kotlin",
    "kotlin": "kotlin",
    "swift": "swift",
    "java": "java",
    "go": "go",
    "cs": "csharp",
    "csharp": "csharp",
    "php": "php",
    "rb": "ruby",
    "ruby": "ruby",
    "rs": "rust",
    "rust": "rust",
    "sql": "sql",
    "xml": "xml",
}

SONAR_TO_VIGILWEAVE_SEVERITY = {
    "BLOCKER": "Critical",
    "CRITICAL": "High",
    "MAJOR": "Medium",
    "MEDIUM": "Medium",
    "MINOR": "Low",
    "LOW": "Low",
    "INFO": "Info",
}

SONAR_TYPE_TO_CATEGORY = {
    "BUG": "reliability",
    "CODE_SMELL": "maintainability",
    "VULNERABILITY": "security",
    "SECURITY_HOTSPOT": "security",
}


def import_sonarqube_rules(
    payload: SonarRulesImportRequest, *, tenant_slug: str
) -> SonarRulesImportResponse:
    """Convert imported SonarQube rules to VigilWeave rule definitions."""

    language = _normalize_language(payload.language)
    converted = _convert_rules(payload.rules, language)
    persisted_path: str | None = None
    if payload.persist:
        persisted_path = _persist_rule_pack(
            tenant_slug=tenant_slug,
            language=language,
            profile_name=payload.profile_name,
            rules=converted,
        )
    return SonarRulesImportResponse(
        language=language,
        profile_name=payload.profile_name,
        rules_imported=len(converted),
        rules=converted,
        persisted_path=persisted_path,
    )


def sync_sonarqube_rules(
    request: SonarRulesSyncRequest, *, tenant_slug: str
) -> SonarRulesSyncResponse:
    """Fetch SonarQube rules from a remote instance and convert them."""

    language = _normalize_language(request.language)
    raw_rules = _fetch_sonarqube_rules(request, language)
    converted = _convert_rules(raw_rules, language)
    persisted_path: str | None = None
    if request.persist:
        persisted_path = _persist_rule_pack(
            tenant_slug=tenant_slug,
            language=language,
            profile_name=request.profile_name or request.quality_profile,
            rules=converted,
        )
    return SonarRulesSyncResponse(
        language=language,
        profile_name=request.profile_name or request.quality_profile,
        rules_imported=len(converted),
        rules=converted,
        persisted_path=persisted_path,
        source_url=request.base_url,
    )


def load_sonarqube_rule_pack(tenant_slug: str, language: str) -> SonarRulesListResponse | None:
    """Load a previously persisted SonarQube-derived rule pack."""

    normalized_language = _normalize_language(language)
    path = _rule_pack_path(tenant_slug, normalized_language)
    if not path.exists():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    updated_at_raw = payload.get("updated_at")
    updated_at: datetime | None = None
    if isinstance(updated_at_raw, str):
        try:
            updated_at = datetime.fromisoformat(updated_at_raw)
        except ValueError:
            updated_at = None

    rules: list[VigilWeaveRuleDefinition] = []
    for item in payload.get("rules", []):
        try:
            rules.append(VigilWeaveRuleDefinition.model_validate(item))
        except ValidationError:
            continue

    return SonarRulesListResponse(
        language=normalized_language,
        profile_name=payload.get("profile_name"),
        rules=rules,
        persisted_path=str(path),
        updated_at=updated_at,
    )


def _fetch_sonarqube_rules(
    request: SonarRulesSyncRequest, normalized_language: str
) -> list[SonarRulePayload]:
    """Fetch SonarQube rules from /api/rules/search using pagination."""

    # Validate URL to prevent SSRF
    ensure_safe_outbound_url(
        request.base_url,
        allow_http=settings.allow_http_outbound,
    )

    page = 1
    collected: list[SonarRulePayload] = []
    headers = _auth_headers(request)
    endpoint = f"{request.base_url.rstrip('/')}/api/rules/search"

    while True:
        params: dict[str, Any] = {
            "languages": normalized_language,
            "ps": request.page_size,
            "p": page,
            "f": (
                "repo,name,lang,severity,type,status,htmlDesc,mdDesc,cleanCodeAttribute,"
                "tags,sysTags,params,impacts"
            ),
        }
        if request.quality_profile:
            params["qprofile"] = request.quality_profile
        if not request.include_inactive:
            params["activation"] = "true"

        response = httpx.get(
            endpoint,
            headers=headers,
            params=params,
            timeout=settings.external_api_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()

        if isinstance(body, dict):
            raw_rules = body.get("rules", [])
            total = int(body.get("total", 0))
        elif isinstance(body, list):
            raw_rules = body
            total = len(raw_rules)
        else:
            raw_rules = []
            total = 0

        page_items = 0
        for item in raw_rules:
            if not isinstance(item, dict):
                continue
            try:
                collected.append(SonarRulePayload.model_validate(item))
                page_items += 1
            except ValidationError:
                continue

        if page_items == 0:
            break
        if total:
            if len(collected) >= total:
                break
        elif page_items < request.page_size:
            break
        page += 1

    return collected


def _auth_headers(request: SonarRulesSyncRequest) -> dict[str, str]:
    auth_scheme = request.auth_scheme.strip().lower()
    if auth_scheme == "basic-token":
        token_bytes = f"{request.token}:".encode("utf-8")
        encoded = base64.b64encode(token_bytes).decode("ascii")
        return {
            "Accept": "application/json",
            "Authorization": f"Basic {encoded}",
        }
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {request.token}",
    }


def _convert_rules(
    rules: list[SonarRulePayload], normalized_language: str
) -> list[VigilWeaveRuleDefinition]:
    converted: list[VigilWeaveRuleDefinition] = []
    seen: set[str] = set()
    for rule in rules:
        mapped = _convert_rule(rule, normalized_language)
        if mapped.vigilweave_rule_id in seen:
            continue
        seen.add(mapped.vigilweave_rule_id)
        converted.append(mapped)
    converted.sort(key=lambda item: item.vigilweave_rule_id)
    return converted


def _convert_rule(rule: SonarRulePayload, normalized_language: str) -> VigilWeaveRuleDefinition:
    source_rule_key = rule.key.strip()
    description = rule.mdDesc or _strip_html(rule.htmlDesc or "")
    category = _map_category(rule.type, rule.tags, rule.sysTags)
    return VigilWeaveRuleDefinition(
        vigilweave_rule_id=_build_rule_id(normalized_language, source_rule_key),
        source="sonarqube",
        source_rule_key=source_rule_key,
        source_repository=rule.repo,
        language=normalized_language,
        title=rule.name.strip() or source_rule_key,
        description=description or None,
        severity=_normalize_severity(rule.severity),
        category=category,
        tags=_rule_tags(rule.tags, rule.sysTags, category),
    )


def _normalize_language(language: str) -> str:
    normalized = language.strip().lower()
    return LANGUAGE_ALIASES.get(normalized, normalized)


def _normalize_severity(severity: str | None) -> str:
    if not severity:
        return "Medium"
    normalized = severity.strip().upper()
    return SONAR_TO_VIGILWEAVE_SEVERITY.get(normalized, "Medium")


def _map_category(rule_type: str | None, tags: list[str], sys_tags: list[str]) -> str:
    if rule_type:
        mapped = SONAR_TYPE_TO_CATEGORY.get(rule_type.strip().upper())
        if mapped:
            return mapped
    tag_set = {tag.strip().lower() for tag in [*tags, *sys_tags] if tag}
    if "security" in tag_set or "cwe" in tag_set or "owasp" in tag_set:
        return "security"
    if "bug" in tag_set:
        return "reliability"
    return "maintainability"


def _rule_tags(tags: list[str], sys_tags: list[str], category: str) -> list[str]:
    merged = [category, *tags, *sys_tags]
    deduped: list[str] = []
    seen: set[str] = set()
    for tag in merged:
        normalized = tag.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value).replace("\n", " ").strip()


def _build_rule_id(language: str, source_rule_key: str) -> str:
    safe_key = re.sub(r"[^a-z0-9:_-]+", "-", source_rule_key.lower()).strip("-")
    return f"sonarqube:{language}:{safe_key}"


def _persist_rule_pack(
    *,
    tenant_slug: str,
    language: str,
    profile_name: str | None,
    rules: list[VigilWeaveRuleDefinition],
) -> str:
    path = _rule_pack_path(tenant_slug, language)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "sonarqube",
        "language": language,
        "profile_name": profile_name,
        "updated_at": datetime.now(UTC).isoformat(),
        "rules": [rule.model_dump() for rule in rules],
    }
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(path)
    return str(path)


def _rule_pack_path(tenant_slug: str, language: str) -> Path:
    base = Path(settings.rulepacks_path).expanduser()
    return base / tenant_slug / f"sonarqube-{language}.json"
