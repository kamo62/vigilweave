"""Versioned repository finding identities and scoped review-state continuity."""

import hashlib
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlmodel import Session, col, select

from app.models import Finding, Scan, ScanStatus

_VERSION = 1
_LIMIT = 1_048_576


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def legacy_fingerprint_digest(value: str) -> str:
    """Encode a historical fingerprint for compatibility matching without storing it raw."""
    return _hash(value)


def _source(root: Path, path: str | None) -> tuple[str, list[str]] | None:
    if not path:
        return None
    try:
        root = root.resolve(strict=True)
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = root / candidate
        relative = candidate.relative_to(root)
        if not relative.parts or any(part in {".", ".."} for part in relative.parts):
            return None
        current = root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                return None
        if not current.resolve(strict=True).is_relative_to(root):
            return None
        fd = os.open(
            current, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        )
        with os.fdopen(fd, "rb") as stream:
            if not os.path.isfile(current):
                return None
            content = stream.read(_LIMIT + 1)
        if len(content) > _LIMIT:
            return None
        return relative.as_posix(), [
            " ".join(line.split()) for line in content.decode("utf-8", "replace").splitlines()
        ]
    except OSError, ValueError, RuntimeError:
        return None


def _secret_values(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in sorted(value.items()):
            if str(key).lower() in {
                "secret",
                "match",
                "token",
                "password",
                "credential",
                "api_key",
            }:
                found.append(str(item))
            else:
                found.extend(_secret_values(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_secret_values(item))
    return found


def assign_identities(root: Path, findings: list[Finding]) -> None:
    """Assign hashes before deduplication, retaining safe legacy aliases only.

    Identical occurrences are ranked by source order; indistinguishable findings at one
    location are ranked in scanner order. Insertions of identical occurrences can shift ranks.
    """
    cache: dict[str, tuple[str, list[str]] | None] = {}
    ranks: defaultdict[str, int] = defaultdict(int)
    for finding in findings:
        original = finding.fingerprint
        metadata = dict(finding.tool_metadata or {})
        key = finding.file_path or ""
        if key not in cache:
            cache[key] = _source(root, finding.file_path)
        source = cache[key]
        aliases: list[str] = []
        aliases.append(_hash(original))
        if source and finding.tool == "quality-analyzer":
            relative = source[0]
            if finding.category == "complexity":
                aliases.append(_hash(f"quality:{relative}:complexity"))
        metadata["original_fingerprint_sha256"] = _hash(original)
        metadata["legacy_fingerprints"] = aliases
        if source:
            relative, lines = source
            line = finding.line or 0
            text = lines[line - 1] if 0 < line <= len(lines) else ""
            occurrence = sum(item == text for item in lines[: max(0, line - 1)]) if text else line
            # Diagnostic content and metadata distinguish multiple results at the same location;
            # only their digest enters the identity.
            discriminator = _hash(
                [
                    finding.message.replace(str(root), "<repo>"),
                    finding.column,
                    _secret_values(finding.tool_metadata),
                ]
            )
            base = _hash(
                [
                    relative,
                    finding.tool,
                    finding.rule_id,
                    finding.category,
                    text,
                    occurrence,
                    discriminator,
                ]
            )
            rank = ranks[base]
            ranks[base] += 1
            finding.fingerprint = "v1:" + _hash([base, rank])
            metadata["identity_version"] = _VERSION
        else:
            # Unresolvable paths cannot provide a repository-relative identity or triage continuity.
            base = _hash(
                [
                    finding.tool,
                    finding.rule_id,
                    finding.category,
                    finding.line,
                    finding.column,
                    finding.message,
                    finding.tool_metadata,
                ]
            )
            rank = ranks[base]
            ranks[base] += 1
            finding.fingerprint = "unresolved:" + _hash([base, rank])
        finding.tool_metadata = metadata


def carry_triage(session: Session, scan: Scan, findings: list[Finding]) -> None:
    """Carry review decisions only from the most recent completed scan in this scope."""
    if scan.project_id is None:
        return
    previous = session.exec(
        select(Scan)
        .where(
            Scan.tenant_slug == scan.tenant_slug,
            Scan.project_id == scan.project_id,
            Scan.repo == scan.repo,
            Scan.branch == scan.branch,
            Scan.status == ScanStatus.COMPLETED,
            Scan.id != scan.id,
        )
        .order_by(col(Scan.completed_at).desc().nulls_last(), col(Scan.id).desc())
    ).first()
    if previous is None:
        return
    old = session.exec(select(Finding).where(Finding.scan_id == previous.id)).all()
    decisions = {
        item.fingerprint: item
        for item in old
        if (item.tool_metadata or {}).get("identity_version") == _VERSION
        and item.fingerprint.startswith("v1:")
    }
    for finding in findings:
        if (finding.tool_metadata or {}).get("identity_version") != _VERSION:
            continue
        prior = decisions.get(finding.fingerprint)
        if prior and prior.review_status in {"acknowledged", "false_positive", "wont_fix"}:
            finding.review_status = prior.review_status
            finding.reviewed_by = prior.reviewed_by
            finding.reviewed_at = prior.reviewed_at
