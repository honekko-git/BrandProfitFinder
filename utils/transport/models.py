"""Request and response models for marketplace HTTP transport."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class TransportRequestMetadata:
    """Common metadata attached to each transport request."""

    marketplace_name: str
    operation: str = "request"
    request_id: str | None = None
    tags: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, str]:
        """Return metadata as a string dictionary for logging."""
        payload: dict[str, str] = {
            "marketplace_name": self.marketplace_name,
            "operation": self.operation,
        }
        if self.request_id:
            payload["request_id"] = self.request_id
        if self.tags:
            payload["tags"] = ",".join(self.tags)
        return payload


@dataclass(frozen=True, slots=True)
class TransportRequest:
    """Canonical HTTP request for marketplace transport."""

    method: str
    url: str
    params: Mapping[str, Any] | None = None
    json: Any | None = None
    data: Any | None = None
    headers: Mapping[str, str] = field(default_factory=dict)
    metadata: TransportRequestMetadata | None = None


@dataclass(frozen=True, slots=True)
class TransportResponse:
    """Validated HTTP response from marketplace transport."""

    status_code: int
    headers: dict[str, str]
    content: bytes
    elapsed_seconds: float
    retry_count: int
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Return response body decoded as UTF-8 text."""
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Parse JSON response body."""
        import json

        return json.loads(self.text)
