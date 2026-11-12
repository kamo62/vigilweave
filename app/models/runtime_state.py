"""Operational persistence models for runtime state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, Index
from sqlmodel import Field, SQLModel


class LicenseVerificationCache(SQLModel, table=True):
    """Database-backed cache for online and offline license verification state."""

    __tablename__ = "license_verification_cache"

    id: int | None = Field(default=None, primary_key=True)
    cache_key: str = Field(index=True, unique=True)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    cached_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)


class WebhookDelivery(SQLModel, table=True):
    """Persisted webhook delivery outcomes for replay protection."""

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index(
            "uq_webhook_deliveries_provider_delivery_id",
            "provider",
            "delivery_id",
            unique=True,
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    provider: str = Field(index=True)
    delivery_id: str = Field(index=True)
    tenant_slug: str | None = Field(default=None, index=True)
    project_id: int | None = Field(default=None, foreign_key="projects.id", ondelete="SET NULL")
    response_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC), index=True)
