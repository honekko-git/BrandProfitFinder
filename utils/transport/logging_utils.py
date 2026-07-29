"""Structured transport logging with secret redaction."""

from __future__ import annotations

import logging
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)

_SENSITIVE_HEADER_NAMES = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "x-api-key",
        "x-auth-token",
        "x-access-token",
        "api-key",
        "apikey",
        "token",
        "cookie",
        "set-cookie",
    }
)
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "access_key",
        "access_token",
        "token",
        "client_secret",
        "secret",
        "password",
        "key",
    }
)
_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key=)[^&\s]+"),
    re.compile(r"(?i)(access[_-]?token=)[^&\s]+"),
    re.compile(r"(?i)(token=)[^&\s]+"),
    re.compile(r"(?i)(secret=)[^&\s]+"),
    re.compile(r"(?i)(password=)[^&\s]+"),
    re.compile(r"(?i)(Bearer\s+)\S+"),
)


def redact_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    """Return headers with sensitive values replaced."""
    if not headers:
        return {}
    redacted: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _SENSITIVE_HEADER_NAMES:
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = value
    return redacted


def redact_url(url: str) -> str:
    """Remove sensitive query parameters from a URL."""
    parsed = urlparse(url)
    if not parsed.query:
        return _redact_secrets_in_text(url)

    query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in _SENSITIVE_QUERY_KEYS:
            query.append((key, "***REDACTED***"))
        else:
            query.append((key, value))
    sanitized = parsed._replace(query=urlencode(query))
    return _redact_secrets_in_text(urlunparse(sanitized))


def _redact_secrets_in_text(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(r"\1***REDACTED***", redacted)
    return redacted


def log_transport_event(
    *,
    level: int,
    event: str,
    marketplace_name: str,
    method: str,
    url: str,
    status_code: int | None,
    retry_count: int,
    elapsed_seconds: float | None,
    headers: Mapping[str, str] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> None:
    """Emit structured transport logs without leaking secrets."""
    payload: dict[str, Any] = {
        "event": event,
        "marketplace_name": marketplace_name,
        "method": method.upper(),
        "request_url": redact_url(url),
        "response_status": status_code,
        "retry_count": retry_count,
        "elapsed_ms": round(elapsed_seconds * 1000, 2) if elapsed_seconds is not None else None,
        "request_headers": redact_headers(headers),
    }
    if extra:
        payload.update(extra)
    logger.log(level, "transport %s marketplace=%s method=%s status=%s retries=%s elapsed_ms=%s", event, marketplace_name, method.upper(), status_code, retry_count, payload["elapsed_ms"], extra={"transport": payload})
