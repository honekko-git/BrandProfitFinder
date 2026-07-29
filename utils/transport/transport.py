"""Shared marketplace HTTP transport for Version 2 live API integration."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Mapping

import httpx

from config.settings import USER_AGENT
from config.transport import DEFAULT_TRANSPORT_SETTINGS, TransportSettings
from utils.transport.exceptions import (
    MarketplaceRateLimitError,
    MarketplaceTransportError,
)
from utils.transport.logging_utils import log_transport_event
from utils.transport.models import TransportRequest, TransportRequestMetadata, TransportResponse
from utils.transport.retry import (
    evaluate_http_status,
    map_request_exception,
    sleep_backoff,
)

logger = logging.getLogger(__name__)


def build_default_headers(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Build default transport headers."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if extra:
        headers.update(dict(extra))
    return headers


@dataclass
class HttpTransport:
    """
    Marketplace HTTP transport with retry, backoff, and structured logging.

    Example::

        transport = HttpTransport(marketplace_name="stockx")
        response = transport.get("https://api.example.com/items", params={"q": "sku"})
        payload = response.json()
    """

    marketplace_name: str
    settings: TransportSettings = field(default_factory=lambda: DEFAULT_TRANSPORT_SETTINGS)
    client: httpx.Client | None = None
    default_headers: Mapping[str, str] = field(default_factory=build_default_headers)

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        metadata: TransportRequestMetadata | None = None,
    ) -> TransportResponse:
        """Execute an HTTP GET request."""
        request = TransportRequest(
            method="GET",
            url=url,
            params=params,
            headers=self._merge_headers(headers),
            metadata=metadata or TransportRequestMetadata(marketplace_name=self.marketplace_name),
        )
        return self.execute(request)

    def post(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        headers: Mapping[str, str] | None = None,
        metadata: TransportRequestMetadata | None = None,
    ) -> TransportResponse:
        """Execute an HTTP POST request."""
        request = TransportRequest(
            method="POST",
            url=url,
            params=params,
            json=json,
            data=data,
            headers=self._merge_headers(headers),
            metadata=metadata or TransportRequestMetadata(marketplace_name=self.marketplace_name),
        )
        return self.execute(request)

    def execute(self, request: TransportRequest) -> TransportResponse:
        """Execute a transport request with retry and response validation."""
        retry_count = 0
        terminal_error: MarketplaceTransportError | None = None

        for attempt in range(self.settings.max_retries + 1):
            started = time.perf_counter()
            try:
                raw = self._send_once(request, retry_count=retry_count)
                elapsed = time.perf_counter() - started
                decision = evaluate_http_status(
                    raw.status_code,
                    marketplace_name=self.marketplace_name,
                    retry_count=retry_count,
                )

                log_transport_event(
                    level=logging.INFO,
                    event="response_received",
                    marketplace_name=self.marketplace_name,
                    method=request.method,
                    url=request.url,
                    status_code=raw.status_code,
                    retry_count=retry_count,
                    elapsed_seconds=elapsed,
                    headers=request.headers,
                    extra=_metadata_dict(request),
                )

                if decision.exception is not None and not decision.should_retry:
                    raise decision.exception

                if decision.should_retry:
                    terminal_error = _terminal_error_for_status(
                        raw.status_code,
                        marketplace_name=self.marketplace_name,
                        retry_count=retry_count,
                    )
                    if attempt < self.settings.max_retries:
                        log_transport_event(
                            level=logging.WARNING,
                            event="retry_scheduled",
                            marketplace_name=self.marketplace_name,
                            method=request.method,
                            url=request.url,
                            status_code=raw.status_code,
                            retry_count=retry_count,
                            elapsed_seconds=elapsed,
                            headers=request.headers,
                            extra=_metadata_dict(request),
                        )
                        sleep_backoff(retry_count, self.settings)
                        retry_count += 1
                        continue
                    raise terminal_error

                return _validate_and_build_response(
                    raw,
                    elapsed_seconds=elapsed,
                    retry_count=retry_count,
                    metadata=_metadata_dict(request),
                )
            except MarketplaceTransportError:
                raise
            except Exception as exc:
                elapsed = time.perf_counter() - started
                decision = map_request_exception(
                    exc,
                    marketplace_name=self.marketplace_name,
                    retry_count=retry_count,
                )
                log_transport_event(
                    level=logging.WARNING,
                    event="request_failed",
                    marketplace_name=self.marketplace_name,
                    method=request.method,
                    url=request.url,
                    status_code=None,
                    retry_count=retry_count,
                    elapsed_seconds=elapsed,
                    headers=request.headers,
                    extra=_metadata_dict(request),
                )
                terminal_error = decision.exception
                if decision.should_retry and attempt < self.settings.max_retries:
                    sleep_backoff(retry_count, self.settings)
                    retry_count += 1
                    continue
                if terminal_error is not None:
                    raise terminal_error
                raise

        if terminal_error is not None:
            raise terminal_error
        raise MarketplaceTransportError(
            "transport failed without response",
            marketplace_name=self.marketplace_name,
            retry_count=retry_count,
        )

    def _send_once(self, request: TransportRequest, *, retry_count: int) -> httpx.Response:
        log_transport_event(
            level=logging.INFO,
            event="request_started",
            marketplace_name=self.marketplace_name,
            method=request.method,
            url=request.url,
            status_code=None,
            retry_count=retry_count,
            elapsed_seconds=None,
            headers=request.headers,
            extra=_metadata_dict(request),
        )
        client = self.client or httpx.Client(timeout=self.settings.timeout_seconds, follow_redirects=True)
        owns_client = self.client is None
        try:
            return client.request(
                request.method,
                request.url,
                params=request.params,
                json=request.json,
                data=request.data,
                headers=dict(request.headers),
            )
        finally:
            if owns_client:
                client.close()

    def _merge_headers(self, headers: Mapping[str, str] | None) -> dict[str, str]:
        merged = dict(self.default_headers)
        if headers:
            merged.update(dict(headers))
        return merged


def _metadata_dict(request: TransportRequest) -> dict[str, str]:
    if request.metadata is None:
        return {"marketplace_name": request.url}
    return request.metadata.as_dict()


def _validate_and_build_response(
    raw: httpx.Response,
    *,
    elapsed_seconds: float,
    retry_count: int,
    metadata: dict[str, str],
) -> TransportResponse:
    if not (200 <= raw.status_code < 300):
        raise MarketplaceTransportError(
            f"unexpected success validation failure for HTTP {raw.status_code}",
            status_code=raw.status_code,
            retry_count=retry_count,
        )
    return TransportResponse(
        status_code=raw.status_code,
        headers={key: value for key, value in raw.headers.items()},
        content=raw.content,
        elapsed_seconds=elapsed_seconds,
        retry_count=retry_count,
        metadata=metadata,
    )


def _terminal_error_for_status(
    status_code: int,
    *,
    marketplace_name: str,
    retry_count: int,
) -> MarketplaceTransportError:
    if status_code == 429:
        return MarketplaceRateLimitError(
            "rate limit exceeded after retries",
            marketplace_name=marketplace_name,
            status_code=status_code,
            retry_count=retry_count,
        )
    if status_code in {500, 502, 503, 504}:
        return MarketplaceTransportError(
            f"server error HTTP {status_code} after retries",
            marketplace_name=marketplace_name,
            status_code=status_code,
            retry_count=retry_count,
        )
    return MarketplaceTransportError(
        f"retryable HTTP {status_code} after retries",
        marketplace_name=marketplace_name,
        status_code=status_code,
        retry_count=retry_count,
    )
