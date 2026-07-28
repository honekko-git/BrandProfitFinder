"""
Yahoo Shopping Product Search API (v3) client.
"""

import json
import logging
from typing import Any
from urllib.parse import urlencode

import httpx

from marketplace.yahoo_exceptions import (
    YahooApiError,
    YahooClientError,
    YahooConfigError,
    YahooRateLimitError,
    YahooResponseError,
    YahooServerError,
)
from marketplace.yahoo_settings import YahooApiSettings

logger = logging.getLogger(__name__)


class YahooApiClient:
    """HTTP client for Yahoo Shopping item search API."""

    def __init__(
        self,
        settings: YahooApiSettings | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        """
        Initialize Yahoo API client.

        Args:
            settings: Yahoo API configuration.
            client: Optional injected httpx client for testing.
        """
        self.settings = settings or YahooApiSettings.from_env()
        self._client = client

    @classmethod
    def from_settings(cls, settings: YahooApiSettings | None = None) -> "YahooApiClient":
        """
        Create client from environment-backed settings.

        Args:
            settings: Optional settings override.

        Returns:
            YahooApiClient instance.
        """
        return cls(settings=settings or YahooApiSettings.from_env())

    def search_items(
        self,
        *,
        query: str | None = None,
        jan_code: str | None = None,
        results: int | None = None,
        start: int = 1,
        in_stock: bool | None = True,
    ) -> dict[str, object]:
        """
        Search Yahoo Shopping items.

        Args:
            query: Search keywords.
            jan_code: JAN code search value.
            results: Maximum number of results to return.
            start: Result offset (1-based).
            in_stock: Restrict to in-stock items when True.

        Returns:
            Parsed JSON response object.

        Raises:
            ValueError: When neither query nor jan_code is provided.
            YahooConfigError: When Client ID is not configured.
            YahooApiError: When the HTTP request fails.
            YahooResponseError: When response JSON is invalid.
        """
        normalized_query = (query or "").strip()
        normalized_jan = (jan_code or "").strip()
        if not normalized_query and not normalized_jan:
            raise ValueError("query or jan_code is required")

        if not self.settings.is_configured:
            raise YahooConfigError("Yahoo Client ID is not configured")

        params: dict[str, str | int | bool] = {
            "appid": self.settings.client_id,
            "results": results if results is not None else self.settings.results,
            "start": max(1, start),
        }
        if normalized_query:
            params["query"] = normalized_query
        if normalized_jan:
            params["jan_code"] = normalized_jan
        if in_stock is not None:
            params["in_stock"] = str(in_stock).lower()

        logger.info(
            "Yahoo item search started (method=%s, results=%s, start=%s)",
            "jan_code" if normalized_jan and not normalized_query else "query",
            params["results"],
            params["start"],
        )

        try:
            response = self._perform_request(params)
        except httpx.TimeoutException as exc:
            logger.error("Yahoo API request timed out")
            raise YahooApiError("Yahoo API request timed out") from exc
        except httpx.RequestError as exc:
            logger.error("Yahoo API connection error: %s", exc.__class__.__name__)
            raise YahooApiError("Yahoo API connection error") from exc

        return self._parse_response(response)

    def _perform_request(self, params: dict[str, str | int | bool]) -> httpx.Response:
        if self._client is not None:
            response = self._client.get(self.settings.base_url, params=params)
        else:
            with httpx.Client(timeout=self.settings.timeout_seconds, follow_redirects=True) as client:
                response = client.get(self.settings.base_url, params=params)

        self._validate_status(response)
        return response

    def _validate_status(self, response: httpx.Response) -> None:
        status = response.status_code
        if status == 429:
            logger.warning("Yahoo API rate limit exceeded (HTTP 429)")
            raise YahooRateLimitError("Yahoo API rate limit exceeded")
        if 400 <= status < 500:
            logger.warning("Yahoo API client error (HTTP %s)", status)
            raise YahooClientError(f"Yahoo API client error: HTTP {status}")
        if status >= 500:
            logger.error("Yahoo API server error (HTTP %s)", status)
            raise YahooServerError(f"Yahoo API server error: HTTP {status}")
        if status >= 400:
            raise YahooApiError(f"Yahoo API error: HTTP {status}")

    @staticmethod
    def _parse_response(response: httpx.Response) -> dict[str, object]:
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type.lower():
            logger.warning("Yahoo API returned non-JSON content-type: %s", content_type)

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            logger.error("Yahoo API JSON decode failed")
            raise YahooResponseError("Yahoo API returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise YahooResponseError("Yahoo API response must be a JSON object")

        hits = payload.get("hits", [])
        hit_count = len(hits) if isinstance(hits, list) else 0
        logger.info("Yahoo item search completed (hits=%d)", hit_count)
        return payload

    @staticmethod
    def mask_params_for_log(params: dict[str, str | int | bool]) -> str:
        """
        Return request parameters safe for logging.

        Args:
            params: Request parameters.

        Returns:
            Query string with appid masked.
        """
        masked = dict(params)
        if "appid" in masked:
            masked["appid"] = "***"
        return urlencode(masked)
