"""HTTP client for live market connector requests."""

from __future__ import annotations

import json
from typing import Any

import httpx

from marketplace.connectors.live.exceptions import MarketConnectorTransportError

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "BrandProfitFinder/1.0",
}


class MarketHttpClient:
    """Minimal HTTP client with timeout, retry, and JSON helpers."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        retry_count: int = 2,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._retry_count = max(0, int(retry_count))
        self._headers = dict(DEFAULT_HEADERS)
        if headers:
            self._headers.update(headers)

    def get_json(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Fetch one JSON response with retry handling."""
        last_error: Exception | None = None
        attempts = self._retry_count + 1
        for _attempt in range(attempts):
            try:
                with httpx.Client(timeout=self._timeout_seconds, headers=self._headers) as client:
                    response = client.get(url, params=params)
                    response.raise_for_status()
                    payload = response.json()
                if not isinstance(payload, dict):
                    raise MarketConnectorTransportError("Live response was not a JSON object")
                return payload
            except (httpx.HTTPError, json.JSONDecodeError, MarketConnectorTransportError) as exc:
                last_error = exc
        message = f"Live market request failed for {url}"
        if last_error is not None:
            message = f"{message}: {last_error}"
        raise MarketConnectorTransportError(message) from last_error
