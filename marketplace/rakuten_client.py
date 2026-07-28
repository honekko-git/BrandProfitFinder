"""
Rakuten Ichiba Item Search API client.
"""

import json
import logging
from typing import Any, Protocol, runtime_checkable

import httpx

from marketplace.rakuten_exceptions import (
    RakutenApiError,
    RakutenClientError,
    RakutenConfigError,
    RakutenNotFoundError,
    RakutenRateLimitError,
    RakutenResponseError,
    RakutenServerError,
    RakutenServiceUnavailableError,
)
from marketplace.rakuten_settings import RakutenConfig

logger = logging.getLogger(__name__)

_ACCESS_KEY_HEADER = "Authorization"


@runtime_checkable
class RakutenClientProtocol(Protocol):
    """Protocol for Rakuten Ichiba search clients."""

    def search_items(
        self,
        *,
        keyword: str,
        hits: int | None = None,
        page: int = 1,
        sort: str | None = None,
    ) -> dict[str, Any]:
        """
        Search Rakuten Ichiba items.

        Args:
            keyword: Search keywords.
            hits: Number of results per page.
            page: Page number (1-based).
            sort: Sort order.

        Returns:
            Parsed JSON response object.
        """
        ...


class FakeRakutenClient:
    """In-memory Rakuten client for tests and demo mode."""

    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        """
        Initialize fake client with optional fixed payload.

        Args:
            payload: JSON response returned by search_items.
        """
        self.payload = payload or {"count": 0, "page": 1, "pageCount": 0, "Items": []}
        self.last_keyword: str = ""
        self.last_hits: int | None = None
        self.last_page: int = 1
        self.last_sort: str | None = None

    def search_items(
        self,
        *,
        keyword: str,
        hits: int | None = None,
        page: int = 1,
        sort: str | None = None,
    ) -> dict[str, Any]:
        """
        Return injected payload and record call parameters.

        Args:
            keyword: Search keywords.
            hits: Number of results per page.
            page: Page number (1-based).
            sort: Sort order.

        Returns:
            Injected JSON response.
        """
        self.last_keyword = keyword
        self.last_hits = hits
        self.last_page = page
        self.last_sort = sort
        return self.payload

    def set_payload(self, payload: dict[str, Any]) -> None:
        """Replace the response payload."""
        self.payload = payload


class RakutenApiClient:
    """HTTP client for Rakuten Ichiba Item Search API (2026-07-01)."""

    def __init__(
        self,
        settings: RakutenConfig | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        """
        Initialize Rakuten API client.

        Args:
            settings: Rakuten API configuration.
            client: Optional injected httpx client for testing.
        """
        self.settings = settings or RakutenConfig.from_env()
        self._client = client

    @classmethod
    def from_settings(cls, settings: RakutenConfig | None = None) -> "RakutenApiClient":
        """
        Create client from environment-backed settings.

        Args:
            settings: Optional settings override.

        Returns:
            RakutenApiClient instance.
        """
        return cls(settings=settings or RakutenConfig.from_env())

    def search_items(
        self,
        *,
        keyword: str,
        hits: int | None = None,
        page: int = 1,
        sort: str | None = None,
    ) -> dict[str, Any]:
        """
        Search Rakuten Ichiba items.

        Args:
            keyword: Search keywords.
            hits: Number of results per page (1-30).
            page: Page number (1-100).
            sort: Sort order override.

        Returns:
            Parsed JSON response object.

        Raises:
            ValueError: When keyword is empty.
            RakutenConfigError: When credentials are not configured.
            RakutenApiError: When the HTTP request fails.
            RakutenResponseError: When response JSON is invalid.
        """
        normalized_keyword = keyword.strip()
        if not normalized_keyword:
            raise ValueError("keyword is required")

        if not self.settings.is_configured:
            raise RakutenConfigError("Rakuten application ID or access key is not configured")

        params: dict[str, str | int] = {
            "applicationId": self.settings.application_id,
            "format": "json",
            "formatVersion": 2,
            "keyword": normalized_keyword,
            "hits": self.settings.validate_hits(hits),
            "page": self.settings.validate_page(page),
            "sort": sort or self.settings.sort,
            "availability": 1,
            "field": 1,
            "imageFlag": 1,
        }
        if self.settings.affiliate_id:
            params["affiliateId"] = self.settings.affiliate_id

        headers = {"Authorization": f"Bearer {self.settings.access_key}"}

        logger.info(
            "Rakuten item search started (hits=%s, page=%s, sort=%s)",
            params["hits"],
            params["page"],
            params["sort"],
        )

        try:
            response = self._perform_request(params, headers)
        except httpx.TimeoutException as exc:
            logger.error("Rakuten API request timed out")
            raise RakutenApiError("Rakuten API request timed out") from exc
        except httpx.RequestError as exc:
            logger.error("Rakuten API connection error: %s", exc.__class__.__name__)
            raise RakutenApiError("Rakuten API connection error") from exc

        return self._parse_response(response)

    def _perform_request(
        self,
        params: dict[str, str | int],
        headers: dict[str, str],
    ) -> httpx.Response:
        attempts = max(1, self.settings.max_retries + 1)
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                if self._client is not None:
                    response = self._client.get(
                        self.settings.base_url,
                        params=params,
                        headers=headers,
                    )
                else:
                    with httpx.Client(
                        timeout=self.settings.timeout_seconds,
                        follow_redirects=True,
                    ) as client:
                        response = client.get(
                            self.settings.base_url,
                            params=params,
                            headers=headers,
                        )
                return self._validate_status(response)
            except (RakutenRateLimitError, RakutenServerError, RakutenServiceUnavailableError) as exc:
                last_error = exc
                if attempt >= attempts:
                    raise
                logger.warning(
                    "Rakuten API retryable error on attempt %d/%d: %s",
                    attempt,
                    attempts,
                    exc.__class__.__name__,
                )

        if last_error is not None:
            raise last_error
        raise RakutenApiError("Rakuten API request failed")

    def _validate_status(self, response: httpx.Response) -> httpx.Response:
        status = response.status_code
        if status == 404:
            logger.info("Rakuten API returned no results (HTTP 404)")
            raise RakutenNotFoundError("Rakuten API returned no results")
        if status == 429:
            logger.warning("Rakuten API rate limit exceeded (HTTP 429)")
            raise RakutenRateLimitError("Rakuten API rate limit exceeded")
        if status == 400:
            logger.warning("Rakuten API parameter error (HTTP 400)")
            raise RakutenClientError("Rakuten API parameter error")
        if status == 503:
            logger.warning("Rakuten API service unavailable (HTTP 503)")
            raise RakutenServiceUnavailableError("Rakuten API service unavailable")
        if status >= 500:
            logger.error("Rakuten API server error (HTTP %s)", status)
            raise RakutenServerError(f"Rakuten API server error: HTTP {status}")
        if status >= 400:
            raise RakutenApiError(f"Rakuten API error: HTTP {status}")
        return response

    @staticmethod
    def _parse_response(response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type.lower():
            logger.warning("Rakuten API returned non-JSON content-type: %s", content_type)

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            logger.error("Rakuten API JSON decode failed")
            raise RakutenResponseError("Rakuten API returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise RakutenResponseError("Rakuten API response must be a JSON object")

        items = payload.get("Items") or payload.get("items") or []
        item_count = len(items) if isinstance(items, list) else 0
        logger.info("Rakuten item search completed (items=%d)", item_count)
        return payload

    @staticmethod
    def empty_result() -> dict[str, Any]:
        """Return an empty Rakuten search result payload."""
        return {
            "count": 0,
            "page": 1,
            "first": 0,
            "last": 0,
            "hits": 0,
            "pageCount": 0,
            "Items": [],
        }

    @staticmethod
    def mask_headers_for_log(headers: dict[str, str]) -> dict[str, str]:
        """
        Return headers safe for logging.

        Args:
            headers: Request headers.

        Returns:
            Headers with access key masked.
        """
        masked = dict(headers)
        if _ACCESS_KEY_HEADER in masked:
            masked[_ACCESS_KEY_HEADER] = "Bearer ***"
        return masked
