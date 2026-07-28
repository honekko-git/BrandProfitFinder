"""
Marketplace factory for creating domestic marketplace instances.
"""

from config.constants import (
    MARKETPLACE_AMAZON_JP,
    MARKETPLACE_FASHIONPHILE,
    MARKETPLACE_GRAILED,
    MARKETPLACE_CHRONO24,
    MARKETPLACE_FARFETCH,
    MARKETPLACE_STOCKX,
    MARKETPLACE_GOAT,
    MARKETPLACE_THEREALREAL,
    MARKETPLACE_LOCAL,
    MARKETPLACE_MERCARI,
    MARKETPLACE_RAKUTEN,
    MARKETPLACE_VESTIAIRE,
    MARKETPLACE_YAHOO,
    MARKETPLACE_YAHOO_AUCTION,
)
from marketplace.amazon_client import AmazonClientProtocol
from marketplace.amazon_marketplace import create_amazon_marketplace
from marketplace.amazon_settings import AmazonConfig
from marketplace.base_marketplace import BaseMarketplace
from marketplace.fashionphile_client import FashionphileClientProtocol
from marketplace.fashionphile_marketplace import create_fashionphile_marketplace
from marketplace.fashionphile_settings import FashionphileSettings
from marketplace.therealreal_client import TheRealRealClientProtocol
from marketplace.therealreal_marketplace import create_therealreal_marketplace
from marketplace.therealreal_settings import TheRealRealSettings
from marketplace.grailed_client import GrailedClientProtocol
from marketplace.grailed_marketplace import create_grailed_marketplace
from marketplace.grailed_settings import GrailedSettings
from marketplace.chrono24_client import Chrono24ClientProtocol
from marketplace.chrono24_marketplace import create_chrono24_marketplace
from marketplace.chrono24_settings import Chrono24Settings
from marketplace.farfetch_client import FarfetchClientProtocol
from marketplace.farfetch_marketplace import create_farfetch_marketplace
from marketplace.farfetch_settings import FarfetchSettings
from marketplace.stockx_client import StockXClientProtocol
from marketplace.stockx_marketplace import create_stockx_marketplace
from marketplace.stockx_settings import StockXSettings
from marketplace.goat_client import GoatClientProtocol
from marketplace.goat_marketplace import create_goat_marketplace
from marketplace.goat_settings import GoatSettings
from marketplace.local_marketplace import LocalMarketplace
from marketplace.rakuten_client import RakutenClientProtocol
from marketplace.rakuten_marketplace import create_rakuten_marketplace
from marketplace.rakuten_settings import RakutenConfig
from marketplace.vestiaire_client import VestiaireClientProtocol
from marketplace.vestiaire_marketplace import create_vestiaire_marketplace
from marketplace.vestiaire_settings import VestiaireSettings
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
_VESTIAIRE_ALIASES = frozenset(
    {"vestiaire", "vestiaire_collective", "vestiaire-collective", "vc"}
)
_FASHIONPHILE_ALIASES = frozenset(
    {"fashionphile", "fashion_phile", "fashion-phile", "fp"}
)
_THEREALREAL_ALIASES = frozenset(
    {"therealreal", "the_real_real", "the-real-real", "realreal", "trr"}
)
_GRAILED_ALIASES = frozenset(
    {"grailed", "grailed_market", "grailed-market", "gr"}
)
_CHRONO24_ALIASES = frozenset(
    {"chrono24", "chrono_24", "chrono-24", "c24"}
)
_FARFETCH_ALIASES = frozenset(
    {"farfetch", "far_fetch", "far-fetch", "ff"}
)
_STOCKX_ALIASES = frozenset(
    {"stockx", "stock_x", "stock-x", "sx"}
)
_GOAT_ALIASES = frozenset(
    {"goat", "goat_marketplace", "goat-marketplace"}
)


def _normalize_marketplace_name(marketplace_name: str) -> str:
    normalized = marketplace_name.strip().lower()
    if normalized in _YAHOO_AUCTION_ALIASES:
        return MARKETPLACE_YAHOO_AUCTION
    if normalized in _VESTIAIRE_ALIASES:
        return MARKETPLACE_VESTIAIRE
    if normalized in _FASHIONPHILE_ALIASES:
        return MARKETPLACE_FASHIONPHILE
    if normalized in _THEREALREAL_ALIASES:
        return MARKETPLACE_THEREALREAL
    if normalized in _GRAILED_ALIASES:
        return MARKETPLACE_GRAILED
    if normalized in _CHRONO24_ALIASES:
        return MARKETPLACE_CHRONO24
    if normalized in _FARFETCH_ALIASES:
        return MARKETPLACE_FARFETCH
    if normalized in _STOCKX_ALIASES:
        return MARKETPLACE_STOCKX
    if normalized in _GOAT_ALIASES:
        return MARKETPLACE_GOAT
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
    vestiaire_settings: VestiaireSettings | None = None,
    vestiaire_client: VestiaireClientProtocol | None = None,
    fashionphile_settings: FashionphileSettings | None = None,
    fashionphile_client: FashionphileClientProtocol | None = None,
    therealreal_settings: TheRealRealSettings | None = None,
    therealreal_client: TheRealRealClientProtocol | None = None,
    grailed_settings: GrailedSettings | None = None,
    grailed_client: GrailedClientProtocol | None = None,
    chrono24_settings: Chrono24Settings | None = None,
    chrono24_client: Chrono24ClientProtocol | None = None,
    farfetch_settings: FarfetchSettings | None = None,
    farfetch_client: FarfetchClientProtocol | None = None,
    stockx_settings: StockXSettings | None = None,
    stockx_client: StockXClientProtocol | None = None,
    goat_settings: GoatSettings | None = None,
    goat_client: GoatClientProtocol | None = None,
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
        vestiaire_settings: Optional Vestiaire settings override.
        vestiaire_client: Optional Vestiaire client override (required for vestiaire).
        fashionphile_settings: Optional Fashionphile settings override.
        fashionphile_client: Optional Fashionphile client override (required for fashionphile).
        therealreal_settings: Optional The RealReal settings override.
        therealreal_client: Optional The RealReal client override (required for therealreal).
        grailed_settings: Optional Grailed settings override.
        grailed_client: Optional Grailed client override (required for grailed).
        chrono24_settings: Optional Chrono24 settings override.
        chrono24_client: Optional Chrono24 client override (required for chrono24).
        farfetch_settings: Optional Farfetch settings override.
        farfetch_client: Optional Farfetch client override (required for farfetch).
        stockx_settings: Optional StockX settings override.
        stockx_client: Optional StockX client override (required for stockx).
        goat_settings: Optional GOAT settings override.
        goat_client: Optional GOAT client override (required for goat).

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

    if normalized == MARKETPLACE_VESTIAIRE.lower():
        return create_vestiaire_marketplace(
            client=vestiaire_client,
            settings=vestiaire_settings,
        )

    if normalized == MARKETPLACE_FASHIONPHILE.lower():
        return create_fashionphile_marketplace(
            client=fashionphile_client,
            settings=fashionphile_settings,
        )

    if normalized == MARKETPLACE_THEREALREAL.lower():
        return create_therealreal_marketplace(
            client=therealreal_client,
            settings=therealreal_settings,
        )

    if normalized == MARKETPLACE_GRAILED.lower():
        return create_grailed_marketplace(
            client=grailed_client,
            settings=grailed_settings,
        )

    if normalized == MARKETPLACE_CHRONO24.lower():
        return create_chrono24_marketplace(
            client=chrono24_client,
            settings=chrono24_settings,
        )

    if normalized == MARKETPLACE_FARFETCH.lower():
        return create_farfetch_marketplace(
            client=farfetch_client,
            settings=farfetch_settings,
        )

    if normalized == MARKETPLACE_STOCKX.lower():
        return create_stockx_marketplace(
            client=stockx_client,
            settings=stockx_settings,
        )

    if normalized == MARKETPLACE_GOAT.lower():
        return create_goat_marketplace(
            client=goat_client,
            settings=goat_settings,
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
    vestiaire_settings: VestiaireSettings | None = None,
    vestiaire_client: VestiaireClientProtocol | None = None,
    fashionphile_settings: FashionphileSettings | None = None,
    fashionphile_client: FashionphileClientProtocol | None = None,
    therealreal_settings: TheRealRealSettings | None = None,
    therealreal_client: TheRealRealClientProtocol | None = None,
    grailed_settings: GrailedSettings | None = None,
    grailed_client: GrailedClientProtocol | None = None,
    chrono24_settings: Chrono24Settings | None = None,
    chrono24_client: Chrono24ClientProtocol | None = None,
    farfetch_settings: FarfetchSettings | None = None,
    farfetch_client: FarfetchClientProtocol | None = None,
    stockx_settings: StockXSettings | None = None,
    stockx_client: StockXClientProtocol | None = None,
    goat_settings: GoatSettings | None = None,
    goat_client: GoatClientProtocol | None = None,
) -> list[BaseMarketplace]:
    """
    Return marketplace instances for all implemented marketplaces.

    Vestiaire, Fashionphile, The RealReal, Grailed, Chrono24, Farfetch, StockX, and GOAT are omitted unless a client is injected.
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
    if vestiaire_client is not None:
        marketplaces.append(
            create_marketplace(
                MARKETPLACE_VESTIAIRE,
                vestiaire_settings=vestiaire_settings,
                vestiaire_client=vestiaire_client,
            )
        )
    if fashionphile_client is not None:
        marketplaces.append(
            create_marketplace(
                MARKETPLACE_FASHIONPHILE,
                fashionphile_settings=fashionphile_settings,
                fashionphile_client=fashionphile_client,
            )
        )
    if therealreal_client is not None:
        marketplaces.append(
            create_marketplace(
                MARKETPLACE_THEREALREAL,
                therealreal_settings=therealreal_settings,
                therealreal_client=therealreal_client,
            )
        )
    if grailed_client is not None:
        marketplaces.append(
            create_marketplace(
                MARKETPLACE_GRAILED,
                grailed_settings=grailed_settings,
                grailed_client=grailed_client,
            )
        )
    if chrono24_client is not None:
        marketplaces.append(
            create_marketplace(
                MARKETPLACE_CHRONO24,
                chrono24_settings=chrono24_settings,
                chrono24_client=chrono24_client,
            )
        )
    if farfetch_client is not None:
        marketplaces.append(
            create_marketplace(
                MARKETPLACE_FARFETCH,
                farfetch_settings=farfetch_settings,
                farfetch_client=farfetch_client,
            )
        )
    if stockx_client is not None:
        marketplaces.append(
            create_marketplace(
                MARKETPLACE_STOCKX,
                stockx_settings=stockx_settings,
                stockx_client=stockx_client,
            )
        )
    if goat_client is not None:
        marketplaces.append(
            create_marketplace(
                MARKETPLACE_GOAT,
                goat_settings=goat_settings,
                goat_client=goat_client,
            )
        )
    return marketplaces
