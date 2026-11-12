"""Tool configuration governance endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.database import get_session
from app.core.security import require_scope
from app.models import (
    ScanTypeConfigItem,
    TenantToolConfigOverridePublic,
    ToolConfigCreate,
    ToolConfigItem,
    ToolConfigPatch,
    ToolConfigSnapshot,
)
from app.services.config_loader import (
    delete_tenant_tool_override,
    get_effective_tool_config,
    get_tenant_tool_override,
    get_tenant_tool_overrides,
    load_tool_config,
    upsert_tenant_tool_override,
)
from app.services.tool_adapters import get_runtime_tool_capabilities

router = APIRouter(prefix="/tool-configs", tags=["tool-configs"])


@router.get("/", response_model=ToolConfigSnapshot)
def get_tool_config_snapshot(
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:read")),
) -> ToolConfigSnapshot:
    """Return full tool configuration and runtime availability."""

    config = get_effective_tool_config(session, principal.tenant_slug)
    base_tools = load_tool_config().get("tools", {})
    overridden = {item.tool for item in get_tenant_tool_overrides(session, principal.tenant_slug)}

    runtime = get_runtime_tool_capabilities()
    tool_items = [
        ToolConfigItem(
            tool=tool_id,
            category=str(raw.get("category", "")),
            languages=[str(language) for language in raw.get("languages", [])],
            enabled=bool(raw.get("enabled", False)),
            runtime_available=runtime.get(
                tool_id, runtime.get(str(raw.get("runner", "")).lower(), False)
            ),
            overridden=tool_id in overridden,
            base_defined=tool_id in base_tools,
            raw=raw,
        )
        for tool_id, raw in config.get("tools", {}).items()
    ]
    scan_type_items = [
        ScanTypeConfigItem(
            name=name,
            categories=[str(category) for category in raw.get("categories", [])],
            tools=[str(tool) for tool in raw.get("tools", [])],
        )
        for name, raw in config.get("scan_types", {}).items()
    ]
    return ToolConfigSnapshot(
        tools=sorted(tool_items, key=lambda item: item.tool),
        scan_types=sorted(scan_type_items, key=lambda item: item.name),
    )


@router.patch("/tools/{tool_id}", response_model=ToolConfigItem)
def patch_tool_config(
    tool_id: str,
    payload: ToolConfigPatch,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> ToolConfigItem:
    """Patch one tenant-scoped tool definition for the current organization."""

    base_tool = load_tool_config().get("tools", {}).get(tool_id)
    override = get_tenant_tool_override(session, principal.tenant_slug, tool_id)
    if base_tool is None and override is None:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")

    _, updated = upsert_tenant_tool_override(
        session,
        principal.tenant_slug,
        tool_id,
        payload.model_dump(exclude_none=True),
    )

    runtime = get_runtime_tool_capabilities()
    runner = str(updated.get("runner", "")).lower()
    return ToolConfigItem(
        tool=tool_id,
        category=str(updated.get("category", "")),
        languages=[str(language) for language in updated.get("languages", [])],
        enabled=bool(updated.get("enabled", False)),
        runtime_available=runtime.get(tool_id, runtime.get(runner, False)),
        overridden=True,
        base_defined=base_tool is not None,
        raw=updated,
    )


@router.put("/tenant/tools/{tool_id}", response_model=ToolConfigItem)
def upsert_tenant_tool_config(
    tool_id: str,
    payload: ToolConfigCreate,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> ToolConfigItem:
    """Create or replace a tenant-scoped tool definition, including custom tool ids."""

    _, updated = upsert_tenant_tool_override(
        session,
        principal.tenant_slug,
        tool_id,
        payload.model_dump(exclude_none=True),
    )
    runtime = get_runtime_tool_capabilities()
    runner = str(updated.get("runner", "")).lower()
    base_tool = load_tool_config().get("tools", {}).get(tool_id)
    return ToolConfigItem(
        tool=tool_id,
        category=str(updated.get("category", "")),
        languages=[str(language) for language in updated.get("languages", [])],
        enabled=bool(updated.get("enabled", False)),
        runtime_available=runtime.get(tool_id, runtime.get(runner, False)),
        overridden=True,
        base_defined=base_tool is not None,
        raw=updated,
    )


@router.get("/tenant/overrides", response_model=list[TenantToolConfigOverridePublic])
def list_tenant_tool_overrides(
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:read")),
) -> list[TenantToolConfigOverridePublic]:
    """List tenant-specific tool overrides."""

    overrides = get_tenant_tool_overrides(session, principal.tenant_slug)
    return [
        TenantToolConfigOverridePublic(
            id=item.id,
            tenant_slug=item.tenant_slug,
            tool=item.tool,
            override=item.override,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in overrides
    ]


@router.delete("/tenant/tools/{tool_id}", status_code=204)
def delete_tenant_tool_config(
    tool_id: str,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> None:
    """Delete one tenant-scoped tool override."""

    deleted = delete_tenant_tool_override(session, principal.tenant_slug, tool_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tenant tool override not found")
