"""
Amazon Product Advertising API live client.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from marketplace.amazon_client import AmazonClientProtocol
from marketplace.amazon_exceptions import (
    AmazonApiError,
    AmazonAuthenticationError,
    AmazonClientError,
    AmazonConfigurationError,
    AmazonRateLimitError,
    AmazonResponseParseError,
    AmazonServerError,
)
from marketplace.amazon_request_signer import AmazonRequestSigner, AmazonSignerConfig, mask_signed_headers_for_log
from marketplace.amazon_response_adapter import adapt_amazon_search_response
from marketplace.amazon_settings import AmazonConfig
from marketplace.amazon_transport_mapper import map_transport_exception

logger = logging.getLogger(__name__)

_SEARCH_PATH = "/paapi5/searchitems"
_SEARCH_RESOURCES = (
    "Images.Primary.Medium",
    "ItemInfo.Title",
    "ItemInfo.ByLineInfo",
    "ItemInfo.ManufactureInfo",
    "ItemInfo.ExternalIds",
    "Offers.Listings.Price",
    "Offers.Listings.DeliveryInfo",
    "Offers.Listings.MerchantInfo",
    "Offers.Listings.Condition",
    "Offers.Listings.Availability",
)


class AmazonApiClient:
    """Live HTTP client for Amazon.co.jp Product Advertising API (PA-API 5.0)."""

    def __init__(
        self,
        config: AmazonConfig | None = None,
        client: httpx.Client | None = None,
        signer: AmazonRequestSigner | None = None,
    ) -> None:
        """
        Initialize Amazon API client.

        Args:
            config: Amazon API configuration.
            client: Optional injected httpx client for testing.
            signer: Optional request signer override for testing.
        """
        self.config = config or AmazonConfig.from_env()
        self._client = client
        self._signer = signer or AmazonRequestSigner(
            AmazonSignerConfig(
                access_key=self.config.access_key,
                secret_key=self.config.secret_key,
                region=self.config.region,
                host=self.config.api_host,
            )
        )

    @classmethod
    def from_settings(cls, config: AmazonConfig | None = None) -> "AmazonApiClient":
        """Create client from environment-backed settings."""
        return cls(config=config or AmazonConfig.from_env())

    def search_items(
        self,
        *,
        query: str,
        page: int = 1,
        max_results: int | None = None,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """
        Search Amazon.co.jp product listings.

        Args:
            query: Search keywords.
            page: Page number (1-based).
            max_results: Maximum number of results to return.
            page_token: Optional pagination token (page number as string).

        Returns:
            Internal standard JSON response for AmazonResponseParser.

        Raises:
            ValueError: When query is empty.
            AmazonConfigurationError: When credentials are not configured.
            AmazonApiError: When the HTTP request fails.
            AmazonResponseParseError: When response adaptation fails.
        """
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query is required")

        if not self.config.is_configured:
            raise AmazonConfigurationError("Amazon API credentials are not configured")

        item_page = self._resolve_item_page(page, page_token)
        item_count = self._resolve_item_count(max_results)
        request_body = self._build_search_request(
            keywords=normalized_query,
            item_page=item_page,
            item_count=item_count,
        )
        body_bytes = json.dumps(request_body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        signed = self._signer.sign(method="POST", path=_SEARCH_PATH, body=body_bytes)

        logger.info(
            "Amazon item search started (page=%s, max_results=%s, transport=%s, headers=%s)",
            item_page,
            item_count,
            self.config.use_transport,
            mask_signed_headers_for_log(signed.headers),
        )

        try:
            if self.config.use_transport:
                raw_payload = self._perform_transport_request(signed)
            else:
                raw_payload = self._perform_request(signed)
        except httpx.TimeoutException as exc:
            logger.error("Amazon API request timed out")
            raise AmazonApiError("Amazon API request timed out") from exc
        except httpx.RequestError as exc:
            logger.error("Amazon API connection error: %s", exc.__class__.__name__)
            raise AmazonApiError("Amazon API connection error") from exc

        try:
            return adapt_amazon_search_response(raw_payload)
        except AmazonResponseParseError:
            raise
        except Exception as exc:
            logger.error("Amazon API response adaptation failed")
            raise AmazonResponseParseError("Amazon API response could not be adapted") from exc

    def _build_search_request(
        self,
        *,
        keywords: str,
        item_page: int,
        item_count: int,
    ) -> dict[str, object]:
        return {
            "Keywords": keywords,
            "SearchIndex": "All",
            "ItemPage": item_page,
            "ItemCount": item_count,
            "PartnerTag": self.config.partner_tag,
            "PartnerType": "Associates",
            "Marketplace": "www.amazon.co.jp",
            "Resources": list(_SEARCH_RESOURCES),
        }

    @staticmethod
    def _resolve_item_page(page: int, page_token: str | None) -> int:
        if page_token:
            try:
                return max(1, int(page_token))
            except ValueError:
                pass
        return max(1, page)

    def _resolve_item_count(self, max_results: int | None) -> int:
        value = max_results if max_results is not None else self.config.max_results
        return max(1, min(10, value))

    def _perform_request(self, signed) -> dict[str, Any]:
        if self._client is not None:
            response = self._client.post(
                signed.url,
                content=signed.body,
                headers=signed.headers,
            )
        else:
            with httpx.Client(timeout=self.config.timeout_seconds, follow_redirects=True) as client:
                response = client.post(
                    signed.url,
                    content=signed.body,
                    headers=signed.headers,
                )
        return self._parse_http_response(response)

    def _perform_transport_request(self, signed) -> dict[str, Any]:
        from config.transport import TransportSettings
        from utils.transport import HttpTransport, TransportRequestMetadata

        base_settings = TransportSettings.from_env()
        transport_settings = TransportSettings(
            timeout_seconds=float(self.config.timeout_seconds),
            max_retries=self.config.retry_count,
            backoff_base_seconds=base_settings.backoff_base_seconds,
            backoff_max_seconds=base_settings.backoff_max_seconds,
        )
        transport = HttpTransport(
            marketplace_name="amazon_jp",
            settings=transport_settings,
            client=self._client,
        )
        metadata = TransportRequestMetadata(
            marketplace_name="amazon_jp",
            operation="search_items",
        )
        try:
            response = transport.post(
                signed.url,
                data=signed.body,
                headers=signed.headers,
                metadata=metadata,
            )
        except Exception as exc:
            mapped = map_transport_exception(exc)
            if isinstance(mapped, AmazonRateLimitError):
                logger.warning("Amazon API rate limit exceeded (HTTP 429)")
            elif isinstance(mapped, AmazonAuthenticationError):
                logger.warning("%s", mapped)
            elif isinstance(mapped, AmazonClientError):
                logger.warning("%s", mapped)
            elif isinstance(mapped, AmazonServerError):
                logger.error("%s", mapped)
            raise mapped from exc

        return self._parse_transport_payload(response)

    @staticmethod
    def _parse_http_response(response: httpx.Response) -> dict[str, Any]:
        AmazonApiClient._validate_status(response)
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise AmazonResponseParseError("Amazon API returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise AmazonResponseParseError("Amazon API response must be a JSON object")
        return payload

    @staticmethod
    def _parse_transport_payload(response) -> dict[str, Any]:
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise AmazonResponseParseError("Amazon API returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise AmazonResponseParseError("Amazon API response must be a JSON object")
        return payload

    @staticmethod
    def _validate_status(response: httpx.Response) -> None:
        status = response.status_code
        if status == 429:
            logger.warning("Amazon API rate limit exceeded (HTTP 429)")
            raise AmazonRateLimitError("Amazon API rate limit exceeded")
        if status in {401, 403}:
            logger.warning("Amazon API authentication failed (HTTP %s)", status)
            raise AmazonAuthenticationError(f"Amazon API authentication failed: HTTP {status}")
        if 400 <= status < 500:
            logger.warning("Amazon API client error (HTTP %s)", status)
            raise AmazonClientError(f"Amazon API client error: HTTP {status}")
        if status >= 500:
            logger.error("Amazon API server error (HTTP %s)", status)
            raise AmazonServerError(f"Amazon API server error: HTTP {status}")

    @staticmethod
    def mask_signed_headers_for_log(headers: dict[str, str]) -> dict[str, str]:
        """Return signed headers safe for logging."""
        return mask_signed_headers_for_log(headers)
