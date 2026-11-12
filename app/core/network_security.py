"""Network and secret-sanitization helpers for integration safety."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "key",
    "password",
    "secret",
    "signature",
    "token",
}

_BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "169.254.169.254",
    "169.254.170.2",
    "100.100.100.200",
    "metadata.google.internal",
}

_TOKEN_PATTERN = re.compile(r"(?i)\b(bearer|basic)\s+[a-z0-9._~+\-/]+=*")
_KV_SECRET_PATTERN = re.compile(
    r"(?i)\b(token|api[_-]?key|password|secret|authorization)\s*[:=]\s*[^\s,;]+"
)
_URL_CREDENTIAL_PATTERN = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^\s/@:]+):([^@\s]+)@")
_URL_USERINFO_PATTERN = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^@\s/]+)@")


def sanitize_url(url: str) -> str:
    """Return a log-safe URL with credentials and secret query params redacted."""

    try:
        parsed = urlsplit(url)
    except Exception:
        return redact_sensitive_text(url)

    netloc = parsed.netloc
    if parsed.username or parsed.password:
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        user = parsed.username or "user"
        user_mask = f"{user[:2]}***" if len(user) > 2 else "***"
        netloc = f"{user_mask}:***@{host}"

    if parsed.query:
        redacted_query: list[tuple[str, str]] = []
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() in _SENSITIVE_QUERY_KEYS:
                redacted_query.append((key, "***"))
            else:
                redacted_query.append((key, value))
        query = urlencode(redacted_query, doseq=True)
    else:
        query = ""

    return urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))


def redact_sensitive_text(text: str) -> str:
    """Best-effort redaction for secrets in logs and error payloads."""

    result = _TOKEN_PATTERN.sub(lambda m: f"{m.group(1)} ***", text)
    result = _KV_SECRET_PATTERN.sub(lambda m: f"{m.group(1)}=***", result)
    result = _URL_CREDENTIAL_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}:***@", result)
    result = _URL_USERINFO_PATTERN.sub(lambda m: f"{m.group(1)}***@", result)
    return result


def ensure_safe_outbound_url(
    url: str,
    *,
    allowed_hosts: list[str] | None = None,
    allow_http: bool = False,
) -> None:
    """Validate outbound URLs to reduce SSRF risk."""

    try:
        parsed = urlsplit(url)
    except Exception as exc:
        raise ValueError("Invalid URL") from exc

    allowed_schemes = {"https"}
    if allow_http:
        allowed_schemes.add("http")

    if parsed.scheme not in allowed_schemes:
        raise ValueError("Invalid URL scheme")

    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise ValueError("URL host is required")

    if host in _BLOCKED_HOSTNAMES or host.endswith(".localhost"):
        raise ValueError("URL host is blocked")

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip is not None and (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise ValueError("URL points to a private or non-routable address")

    if allowed_hosts and not _is_allowed_host(host, allowed_hosts):
        raise ValueError("URL host is not in the allowed list")


def is_private_hostname(host: str) -> bool:
    """Return whether a hostname resolves to obviously private/local-only space by syntax."""

    normalized = host.strip().lower().rstrip(".")
    if not normalized:
        return True
    if normalized in _BLOCKED_HOSTNAMES or normalized.endswith(".localhost"):
        return True

    try:
        ip = ipaddress.ip_address(normalized)
    except ValueError:
        ip = None

    if ip is not None:
        return bool(
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )

    return normalized.endswith(".internal") or normalized.endswith(".local")


def is_safe_repo_url(repo_url: str) -> bool:
    """Return whether a repository URL uses an allowed scheme."""

    parsed = urlsplit(repo_url)
    return parsed.scheme in {"https", "file"}


def _is_allowed_host(hostname: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        candidate = pattern.strip().lower().rstrip(".")
        if not candidate:
            continue
        if candidate.startswith("*."):
            domain = candidate[2:]
            if hostname == domain or hostname.endswith(f".{domain}"):
                return True
            continue
        if hostname == candidate:
            return True
    return False
