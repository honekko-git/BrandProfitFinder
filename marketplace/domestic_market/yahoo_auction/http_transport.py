"""HTTP transport for Yahoo Auction sold listing data."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from marketplace.domestic_market.yahoo_auction.exceptions import (
    YahooAuctionAuthenticationError,
    YahooAuctionResponseError,
    YahooAuctionTransportError,
)

if TYPE_CHECKING:
    from marketplace.domestic_market.config import DomesticMarketRuntimeConfig

logger = logging.getLogger(__name__)


class YahooAuctionHTTPTransport:
    """Fetch sold Yahoo Auction listings over HTTP."""

    def __init__(
        self,
        *,
        config: DomesticMarketRuntimeConfig,
        client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._client = client

    def search_sold_items(self, query: str) -> list[dict[str, object]]:
        """Search sold listings and return normalized transport payloads."""
        normalized_query = query.strip()
        if not normalized_query:
            raise YahooAuctionTransportError("Yahoo Auction search query must not be blank")

        endpoint = self._config.endpoint
        if not endpoint or not endpoint.strip():
            raise YahooAuctionTransportError("Yahoo Auction HTTP endpoint is not configured")

        api_key = self._config.api_key
        if not api_key or not api_key.strip():
            raise YahooAuctionAuthenticationError("Yahoo Auction API key is not configured")

        params = self.build_request_params(normalized_query, api_key=api_key.strip())
        logger.debug(
            "Yahoo Auction HTTP search started (endpoint=%s, query=%s, timeout=%ss, retries=%s)",
            endpoint,
            normalized_query,
            self._config.timeout_seconds,
            self._config.retry_count,
        )

        try:
            response = self._request_with_retry(endpoint.strip(), params)
        except httpx.TimeoutException as exc:
            raise YahooAuctionTransportError("Yahoo Auction HTTP request timed out") from exc
        except httpx.NetworkError as exc:
            raise YahooAuctionTransportError("Yahoo Auction HTTP connection failed") from exc

        return self.parse_response_payload(response)

    @staticmethod
    def build_request_params(query: str, *, api_key: str) -> dict[str, str]:
        """Build query parameters for one sold-listing search request."""
        return {
            "query": query,
            "appid": api_key,
        }

    def _request_with_retry(self, endpoint: str, params: dict[str, str]) -> httpx.Response:
        attempts = max(1, self._config.retry_count)

        @retry(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=0.1, min=0.1, max=1.0),
            retry=retry_if_exception_type(YahooAuctionTransportError),
            reraise=True,
        )
        def _perform() -> httpx.Response:
            return self._perform_request(endpoint, params)

        return _perform()

    def _perform_request(self, endpoint: str, params: dict[str, str]) -> httpx.Response:
        timeout = httpx.Timeout(self._config.timeout_seconds)
        if self._client is not None:
            response = self._client.get(endpoint, params=params, timeout=timeout)
        else:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.get(endpoint, params=params)

        status = response.status_code
        if status in (401, 403):
            raise YahooAuctionAuthenticationError(
                f"Yahoo Auction authentication failed: HTTP {status}"
            )
        if status >= 500:
            raise YahooAuctionTransportError(f"Yahoo Auction server error: HTTP {status}")
        if status >= 400:
            raise YahooAuctionResponseError(f"Yahoo Auction client error: HTTP {status}")
        return response

    @staticmethod
    def parse_response_payload(response: httpx.Response) -> list[dict[str, object]]:
        """Validate and normalize one HTTP JSON response."""
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise YahooAuctionResponseError("Yahoo Auction response is not valid JSON") from exc

        raw_items = _extract_items(payload)
        if not isinstance(raw_items, list):
            raise YahooAuctionResponseError("Yahoo Auction response items must be a list")

        validated: list[dict[str, object]] = []
        for index, item in enumerate(raw_items):
            normalized = _validate_item(item)
            if normalized is None:
                raise YahooAuctionResponseError(
                    f"Yahoo Auction response item at index {index} is missing required fields"
                )
            validated.append(normalized)
        return validated


def _extract_items(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        items = payload.get("items", payload.get("listings"))
        if isinstance(items, list):
            return items
    raise YahooAuctionResponseError("Yahoo Auction response must contain sold listing items")


def _validate_item(item: object) -> dict[str, object] | None:
    if not isinstance(item, dict):
        return None
    title = item.get("title")
    sold_price = item.get("sold_price", item.get("price_jpy"))
    if not title or sold_price is None:
        return None
    try:
        price = int(sold_price)
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None

    normalized: dict[str, object] = {
        "title": str(title).strip(),
        "sold_price": price,
    }
    if item.get("url") is not None:
        normalized["url"] = str(item["url"])
    if item.get("sold_date") is not None:
        normalized["sold_date"] = str(item["sold_date"])
    return normalized
