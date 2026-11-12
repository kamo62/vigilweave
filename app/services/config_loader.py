"""Tool configuration loader."""

from copy import deepcopy
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any

import yaml
from sqlmodel import Session, select

from app.models import TenantToolConfigOverride

CONFIG_PATH = Path(__file__).resolve().parents[2] / "tools_config.yaml"
_CONFIG_LOCK = Lock()


@lru_cache
def load_tool_config() -> dict[str, Any]:
    """Load scanning configuration from YAML."""

    with CONFIG_PATH.open("r", encoding="utf-8") as file_handle:
        return yaml.safe_load(file_handle)


def get_effective_tool_config(
    session: Session | None = None, tenant_slug: str | None = None
) -> dict[str, Any]:
    """Load base config and merge tenant-specific overrides when provided."""

    config = deepcopy(load_tool_config())
    if session is None or tenant_slug is None:
        return config

    tools = config.setdefault("tools", {})
    overrides = list(
        session.exec(
            select(TenantToolConfigOverride).where(
                TenantToolConfigOverride.tenant_slug == tenant_slug
            )
        ).all()
    )
    for record in overrides:
        merged = dict(tools.get(record.tool, {}))
        merged.update(dict(record.override or {}))
        tools[record.tool] = _normalize_tool_config(merged)
    return config


def get_enabled_tools(config: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Return enabled tool definitions."""

    tools = (config or load_tool_config()).get("tools", {})
    return {tool: config for tool, config in tools.items() if config.get("enabled", False)}


def get_tools_for_scan_type(scan_type: str, config: dict[str, Any] | None = None) -> list[str]:
    """Return tool ids configured for a scan type."""

    effective_config = config or load_tool_config()
    tools = get_enabled_tools(effective_config)
    scan_types = effective_config.get("scan_types", {})
    selected = scan_types.get(scan_type, {})
    explicit_tools = selected.get("tools", [])
    if explicit_tools:
        return [tool for tool in explicit_tools if tool in tools]

    categories = set(selected.get("categories", []))
    return [
        tool for tool, tool_config in tools.items() if tool_config.get("category") in categories
    ]


def clear_tool_config_cache() -> None:
    """Clear cached tool configuration."""

    load_tool_config.cache_clear()


def update_tool_definition(tool_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Patch and persist a single tool definition."""

    with _CONFIG_LOCK:
        config = load_tool_config()
        tools = config.setdefault("tools", {})
        if tool_id not in tools:
            raise KeyError(tool_id)
        tool_config = dict(tools[tool_id])
        tool_config.update(patch)
        tools[tool_id] = _normalize_tool_config(tool_config)
        with CONFIG_PATH.open("w", encoding="utf-8") as file_handle:
            yaml.safe_dump(config, file_handle, sort_keys=False)
    clear_tool_config_cache()
    return load_tool_config()["tools"][tool_id]


def get_tenant_tool_overrides(session: Session, tenant_slug: str) -> list[TenantToolConfigOverride]:
    """Return all tool overrides for a tenant."""

    return list(
        session.exec(
            select(TenantToolConfigOverride).where(
                TenantToolConfigOverride.tenant_slug == tenant_slug
            )
        ).all()
    )


def get_tenant_tool_override(
    session: Session, tenant_slug: str, tool_id: str
) -> TenantToolConfigOverride | None:
    """Return one tool override for a tenant."""

    return session.exec(
        select(TenantToolConfigOverride).where(
            TenantToolConfigOverride.tenant_slug == tenant_slug,
            TenantToolConfigOverride.tool == tool_id,
        )
    ).first()


def upsert_tenant_tool_override(
    session: Session,
    tenant_slug: str,
    tool_id: str,
    patch: dict[str, Any],
) -> tuple[TenantToolConfigOverride, dict[str, Any]]:
    """Create or update a tenant-specific override and return the effective tool config."""

    record = get_tenant_tool_override(session, tenant_slug, tool_id)
    merged_override = dict(record.override if record else {})
    merged_override.update(patch)
    normalized_override = _normalize_tool_config(merged_override)

    now = datetime.now(UTC)
    if record is None:
        record = TenantToolConfigOverride(
            tenant_slug=tenant_slug,
            tool=tool_id,
            override=normalized_override,
            created_at=now,
            updated_at=now,
        )
    else:
        record.override = normalized_override
        record.updated_at = now

    session.add(record)
    session.commit()
    session.refresh(record)

    effective = get_effective_tool_config(session, tenant_slug).get("tools", {}).get(tool_id, {})
    return record, effective


def delete_tenant_tool_override(session: Session, tenant_slug: str, tool_id: str) -> bool:
    """Delete a tenant tool override if it exists."""

    record = get_tenant_tool_override(session, tenant_slug, tool_id)
    if record is None:
        return False
    session.delete(record)
    session.commit()
    return True


def _normalize_tool_config(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(raw)
    if "languages" in normalized:
        normalized["languages"] = sorted(
            {
                str(language).strip().lower()
                for language in normalized.get("languages", [])
                if str(language).strip()
            }
        )
    if "runner" in normalized and normalized.get("runner") is not None:
        normalized["runner"] = str(normalized["runner"]).strip().lower()
    return normalized
