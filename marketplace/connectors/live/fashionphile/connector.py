"""Live Fashionphile market connector."""

from __future__ import annotations

from marketplace.connectors.base import MarketConnectorUnavailableError
from marketplace.connectors.config import MarketConnectorConfig
from marketplace.connectors.live.base import LiveConnectorBase
from marketplace.connectors.live.fashionphile.parser import parse_fashionphile_response
from marketplace.connectors.live.http_client import MarketHttpClient
from marketplace.connectors.models import MarketListing


class FashionphileLiveConnector(LiveConnectorBase):
    """Fetch overseas used-luxury purchase candidates from Fashionphile."""

    MARKET_NAME = "Fashionphile"

    def __init__(
        self,
        *,
        config: MarketConnectorConfig | None = None,
        http_client: MarketHttpClient | None = None,
        api_url: str | None = None,
    ) -> None:
        super().__init__(config=config, http_client=http_client)
        self._api_url = (api_url if api_url is not None else self._config.fashionphile_api_url).strip()
        self._cache: list[MarketListing] = []

    @property
    def market_name(self) -> str:
        return self.MARKET_NAME

    @property
    def source_type(self) -> str:
        return "LIVE"

    def search_products(self, query: str) -> list[MarketListing]:
        if not self._api_url:
            raise MarketConnectorUnavailableError("Fashionphile API URL is not configured")
        payload = self._http.get_json(self._api_url, params={"q": query.strip()})
        self._cache = parse_fashionphile_response(payload)
        return list(self._cache)

    def get_product(self, url: str) -> MarketListing | None:
        normalized = url.strip()
        for listing in self._cache:
            if listing.url == normalized:
                return listing
        return None
