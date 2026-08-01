"""Runtime configuration for domestic market client selection."""

from __future__ import annotations

from dataclasses import dataclass

from marketplace.domestic_market.yahoo_auction.config import TransportMode


@dataclass(frozen=True, slots=True)
class DomesticMarketRuntimeConfig:
    """Controls whether domestic market resolution prefers fixture or live clients."""

    use_fixture: bool = True
    enable_live: bool = False
    api_key: str | None = None
    transport_mode: TransportMode = TransportMode.FIXTURE
    endpoint: str | None = None
    timeout_seconds: float = 10
    retry_count: int = 3

    @classmethod
    def default(cls) -> DomesticMarketRuntimeConfig:
        """Return the default runtime configuration."""
        return cls()

    @classmethod
    def fixture_only(cls) -> DomesticMarketRuntimeConfig:
        """Return configuration that resolves fixture clients only."""
        return cls(use_fixture=True, enable_live=False, transport_mode=TransportMode.FIXTURE)

    @classmethod
    def live_only(cls, *, api_key: str) -> DomesticMarketRuntimeConfig:
        """Return configuration that attempts live clients only."""
        return cls(
            use_fixture=False,
            enable_live=True,
            api_key=api_key,
            transport_mode=TransportMode.LIVE,
        )

    def prefers_live(self) -> bool:
        """Return True when live Yahoo Auction transport should be attempted."""
        return self.transport_mode is TransportMode.LIVE or self.enable_live

    def is_live_configured(self) -> bool:
        """Return True when live Yahoo Auction access is configured."""
        return self.prefers_live() and bool(self.api_key and self.api_key.strip())

    def is_http_transport_configured(self) -> bool:
        """Return True when HTTP live Yahoo Auction transport can be constructed."""
        return (
            self.is_live_configured()
            and bool(self.endpoint and self.endpoint.strip())
        )

    @classmethod
    def from_cli_live_market(cls) -> DomesticMarketRuntimeConfig:
        """Build live-market runtime config for discovery CLI activation."""
        from config.settings import (
            YAHOO_AUCTION_DATA_SOURCE,
            YAHOO_AUCTION_MAX_RETRIES,
            YAHOO_AUCTION_TIMEOUT,
            YAHOO_CLIENT_ID,
        )

        retry_count = YAHOO_AUCTION_MAX_RETRIES if YAHOO_AUCTION_MAX_RETRIES > 0 else 3
        return cls(
            use_fixture=True,
            enable_live=True,
            api_key=YAHOO_CLIENT_ID or None,
            transport_mode=TransportMode.LIVE,
            endpoint=YAHOO_AUCTION_DATA_SOURCE or None,
            timeout_seconds=float(YAHOO_AUCTION_TIMEOUT),
            retry_count=retry_count,
        )
