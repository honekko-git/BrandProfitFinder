"""
Marketplace factory for creating domestic marketplace instances.
"""

from config.constants import (
    MARKETPLACE_AMAZON_JP,
    MARKETPLACE_LOCAL,
    MARKETPLACE_MERCARI,
    MARKETPLACE_RAKUTEN,
    MARKETPLACE_YAHOO,
    MARKETPLACE_YAHOO_AUCTION,
)
from marketplace.amazon_client import AmazonClientProtocol
from marketplace.amazon_marketplace import create_amazon_marketplace
from marketplace.amazon_settings import AmazonConfig
from marketplace.base_marketplace import BaseMarketplace
from marketplace.local_marketplace import LocalMarketplace
from marketplace.rakuten_client import RakutenClientProtocol
from marketplace.rakuten_marketplace import create_rakuten_marketplace
from marketplace.rakuten_settings import RakutenConfig
from marketplace.yahoo_auction_client import YahooAuctionClientProtocol
from marketplace.yahoo_auction_marketplace import create_yahoo_auction_marketplace
from marketplace.yahoo_auction_settings import YahooAuctionConfig
from marketplace.yahoo_marketplace import create_yahoo_marketplace
from marketplace.yahoo_settings import YahooApiSettings
from models.marketplace_listing import MarketplaceListing
from price_compare.price_comparator import PriceSelectionStrategy

_YAHOO_AUCTION_ALIASES = frozenset(
    {"yahoo_auction", "yahoo-auction", "yahooauction", "auctions"}
)


def _normalize_marketplace_name(marketplace_name: str) -> str:
    normalized = marketplace_name.strip().lower()
    if normalized in _YAHOO_AUCTION_ALIASES:
        return MARKETPLACE_YAHOO_AUCTION
    return normalized


def create_marketplace(
    marketplace_name: str,
    listings_by_product_key: dict[str, list[MarketplaceListing]] | None = None,
    selection_strategy: PriceSelectionStrategy = PriceSelectionStrategy.HIGHEST,
    yahoo_settings: YahooApiSettings | None = None,
    amazon_settings: AmazonConfig | None = None,
    amazon_client: AmazonClientProtocol | None = None,
    rakuten_settings: RakutenConfig | None = None,
    rakuten_client: RakutenClientProtocol | None = None,
    yahoo_auction_settings: YahooAuctionConfig | None = None,
    yahoo_auction_client: YahooAuctionClientProtocol | None = None,
) -> BaseMarketplace:
    """
    Create a marketplace instance for the given name.

    Args:
        marketplace_name: Marketplace identifier (case-insensitive).
        listings_by_product_key: Optional injected listings for local marketplace.
        selection_strategy: Price selection strategy.
        yahoo_settings: Optional Yahoo settings override.
        amazon_settings: Optional Amazon settings override.
        amazon_client: Optional Amazon client override.
        rakuten_settings: Optional Rakuten settings override.
        rakuten_client: Optional Rakuten client override.
        yahoo_auction_settings: Optional Yahoo Auction settings override.
        yahoo_auction_client: Optional Yahoo Auction client override.

    Returns:
        Configured marketplace instance.

    Raises:
        ValueError: When marketplace is not supported or not yet implemented.
    """
    normalized = _normalize_marketplace_name(marketplace_name)
    if normalized == MARKETPLACE_LOCAL.lower():
        return LocalMarketplace(
            listings_by_product_key=listings_by_product_key,
            selection_strategy=selection_strategy,
        )

    if normalized == MARKETPLACE_YAHOO.lower():
        return create_yahoo_marketplace(settings=yahoo_settings)

    if normalized in {MARKETPLACE_AMAZON_JP.lower(), "amazon"}:
        return create_amazon_marketplace(client=amazon_client, config=amazon_settings)

    if normalized == MARKETPLACE_RAKUTEN.lower():
        return create_rakuten_marketplace(client=rakuten_client, config=rakuten_settings)

    if normalized == MARKETPLACE_YAHOO_AUCTION.lower():
        return create_yahoo_auction_marketplace(
            client=yahoo_auction_client,
            config=yahoo_auction_settings,
        )

    not_implemented = {
        MARKETPLACE_MERCARI.lower(): "Mercari marketplace is not yet implemented",
    }
    if normalized in not_implemented:
        raise ValueError(not_implemented[normalized])

    raise ValueError(f"Unsupported marketplace: {marketplace_name}")


def get_all_marketplaces(
    listings_by_product_key: dict[str, list[MarketplaceListing]] | None = None,
    yahoo_settings: YahooApiSettings | None = None,
    amazon_settings: AmazonConfig | None = None,
    amazon_client: AmazonClientProtocol | None = None,
    rakuten_settings: RakutenConfig | None = None,
    rakuten_client: RakutenClientProtocol | None = None,
    yahoo_auction_settings: YahooAuctionConfig | None = None,
    yahoo_auction_client: YahooAuctionClientProtocol | None = None,
) -> list[BaseMarketplace]:
    """
    Return marketplace instances for all implemented marketplaces.

    Args:
        listings_by_product_key: Optional injected listings for local marketplace.
        yahoo_settings: Optional Yahoo settings override.
        amazon_settings: Optional Amazon settings override.
        amazon_client: Optional Amazon client override.
        rakuten_settings: Optional Rakuten settings override.
        rakuten_client: Optional Rakuten client override.
        yahoo_auction_settings: Optional Yahoo Auction settings override.
        yahoo_auction_client: Optional Yahoo Auction client override.

    Returns:
        List of marketplace instances.
    """
    yahoo = yahoo_settings or YahooApiSettings.from_env()
    amazon = amazon_settings or AmazonConfig.from_env()
    rakuten = rakuten_settings or RakutenConfig.from_env()
    yahoo_auction = yahoo_auction_settings or YahooAuctionConfig.from_env()
    marketplaces: list[BaseMarketplace] = [
        create_marketplace(MARKETPLACE_LOCAL, listings_by_product_key=listings_by_product_key),
        create_marketplace(MARKETPLACE_YAHOO, yahoo_settings=yahoo),
        create_marketplace(
            MARKETPLACE_AMAZON_JP,
            amazon_settings=amazon,
            amazon_client=amazon_client,
        ),
        create_marketplace(
            MARKETPLACE_RAKUTEN,
            rakuten_settings=rakuten,
            rakuten_client=rakuten_client,
        ),
        create_marketplace(
            MARKETPLACE_YAHOO_AUCTION,
            yahoo_auction_settings=yahoo_auction,
            yahoo_auction_client=yahoo_auction_client,
        ),
    ]
    return marketplaces
