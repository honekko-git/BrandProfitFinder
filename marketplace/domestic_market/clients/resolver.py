"""Domestic market client resolution for fixture and live Yahoo Auction sources."""



from __future__ import annotations



from dataclasses import dataclass

from enum import StrEnum



from marketplace.domestic_market.base import DomesticMarketClient

from marketplace.domestic_market.clients.yahoo import YahooAuctionDomesticMarketClient

from marketplace.domestic_market.config import DomesticMarketRuntimeConfig

from marketplace.domestic_market.execution import (

    MarketExecutionResult,

    requested_mode_from_config,

    resolve_actual_source,

    resolve_client_name,

    wrap_with_execution_tracking,

)

from marketplace.domestic_market.yahoo_auction.config import TransportMode

from marketplace.domestic_market.yahoo_auction.exceptions import YahooAuctionLiveUnavailableError

from marketplace.domestic_market.yahoo_auction.fallback_client import YahooAuctionFallbackDomesticMarketClient

from marketplace.domestic_market.yahoo_auction.http_transport import YahooAuctionHTTPTransport

from marketplace.domestic_market.yahoo_auction.live_client import YahooAuctionLiveDomesticMarketClient

from marketplace.domestic_market.yahoo_auction.transport import YahooAuctionTransport

from marketplace.yahoo_auction.client import FakeYahooAuctionClient





class DomesticMarketSourceMode(StrEnum):

    """Resolved domestic market data source mode."""



    INJECTED = "INJECTED"

    LIVE = "LIVE"

    FIXTURE = "FIXTURE"





@dataclass(frozen=True, slots=True)

class DomesticMarketClientResolution:

    """Result of resolving one domestic market client."""



    market_name: str

    client: DomesticMarketClient | None

    mode: DomesticMarketSourceMode | None = None

    execution: MarketExecutionResult | None = None





class DomesticMarketClientResolver:

    """Resolve Yahoo Auction domestic clients with injection, live, then fixture priority."""



    def __init__(self, config: DomesticMarketRuntimeConfig | None = None) -> None:

        self._config = config or DomesticMarketRuntimeConfig.default()



    @property

    def config(self) -> DomesticMarketRuntimeConfig:

        return self._config



    def resolve_yahoo_auction(

        self,

        *,

        injected_client: DomesticMarketClient | None = None,

        injected_transport: YahooAuctionTransport | None = None,

    ) -> DomesticMarketClientResolution:

        """Resolve the Yahoo Auction domestic market client."""

        requested_mode = requested_mode_from_config(self._config)



        if injected_client is not None:
            return DomesticMarketClientResolution(
                market_name="yahoo_auction",
                client=injected_client,
                mode=DomesticMarketSourceMode.INJECTED,
                execution=MarketExecutionResult(
                    requested_mode=requested_mode,
                    actual_source=resolve_actual_source(
                        client=injected_client,
                        live=injected_client.market_name.endswith("_live"),
                    ),
                    fallback_used=False,
                    client_name=resolve_client_name(injected_client),
                ),
            )



        fixture_client = (

            YahooAuctionDomesticMarketClient(FakeYahooAuctionClient())

            if self._config.use_fixture

            else None

        )



        if self._config.prefers_live():

            transport = injected_transport

            if transport is None and self._config.is_http_transport_configured():

                transport = YahooAuctionHTTPTransport(config=self._config)

            live_client = YahooAuctionLiveDomesticMarketClient(

                config=self._config,

                transport=transport,

            )

            if _is_live_client_available(live_client):

                if fixture_client is not None and self._config.use_fixture:

                    client: DomesticMarketClient = YahooAuctionFallbackDomesticMarketClient(

                        primary=live_client,

                        fallback=fixture_client,

                        requested_mode=requested_mode,

                    )

                    return DomesticMarketClientResolution(

                        market_name="yahoo_auction",

                        client=client,

                        mode=DomesticMarketSourceMode.LIVE,

                        execution=MarketExecutionResult(

                            requested_mode=requested_mode,

                            actual_source="Yahoo Auction LIVE",

                            fallback_used=False,

                            client_name=resolve_client_name(live_client),

                        ),

                    )

                client = wrap_with_execution_tracking(live_client, requested_mode=requested_mode)

                return DomesticMarketClientResolution(

                    market_name="yahoo_auction",

                    client=client,

                    mode=DomesticMarketSourceMode.LIVE,

                    execution=MarketExecutionResult(

                        requested_mode=requested_mode,

                        actual_source="Yahoo Auction LIVE",

                        fallback_used=False,

                        client_name=resolve_client_name(live_client),

                    ),

                )

            if fixture_client is not None:

                client = wrap_with_execution_tracking(fixture_client, requested_mode=requested_mode)

                return DomesticMarketClientResolution(

                    market_name="yahoo_auction",

                    client=client,

                    mode=DomesticMarketSourceMode.FIXTURE,

                    execution=MarketExecutionResult(

                        requested_mode=requested_mode,

                        actual_source="Fixture",

                        fallback_used=True,

                        client_name=resolve_client_name(fixture_client),

                    ),

                )

            return DomesticMarketClientResolution(

                market_name="yahoo_auction",

                client=None,

                mode=None,

                execution=None,

            )



        if self._config.transport_mode is TransportMode.FIXTURE and fixture_client is not None:

            client = wrap_with_execution_tracking(fixture_client, requested_mode=requested_mode)

            return DomesticMarketClientResolution(

                market_name="yahoo_auction",

                client=client,

                mode=DomesticMarketSourceMode.FIXTURE,

                execution=MarketExecutionResult(

                    requested_mode=requested_mode,

                    actual_source="Fixture",

                    fallback_used=False,

                    client_name=resolve_client_name(fixture_client),

                ),

            )



        return DomesticMarketClientResolution(

            market_name="yahoo_auction",

            client=None,

            mode=None,

            execution=None,

        )





def _is_live_client_available(client: YahooAuctionLiveDomesticMarketClient) -> bool:

    if client.transport is not None:

        return True

    try:

        client.search_sold_prices("__availability_probe__")

        return True

    except YahooAuctionLiveUnavailableError:

        return False


