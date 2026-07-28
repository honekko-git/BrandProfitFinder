"""
BrandProfitFinder application entry point.

Phase 3/4/5A: domestic marketplace candidates, profit calculation, and Excel export.
Default execution uses local marketplace without external network access.
"""

import json
import logging
import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from config.logging_config import setup_logging
from config.settings import (
    AMAZON_JP_DEMO_ENABLED,
    AMAZON_JP_ENABLED,
    DEFAULT_EXCHANGE_RATE,
    EXCEL_FILENAME,
    OUTPUT_DIR,
    RAKUTEN_API_DEMO_ENABLED,
    RAKUTEN_API_ENABLED,
    YAHOO_API_ENABLED,
    YAHOO_AUCTION_DEMO_ENABLED,
    YAHOO_AUCTION_ENABLED,
    USED_LUXURY_DEMO_ENABLED,
    VESTIAIRE_DEMO_ENABLED,
    FASHIONPHILE_DEMO_ENABLED,
    THEREALREAL_DEMO_ENABLED,
)
from excel.exporter import ExcelExporter
from marketplace.amazon_client import FakeAmazonClient
from marketplace.amazon_settings import AmazonConfig
from marketplace.marketplace_factory import create_marketplace
from marketplace.rakuten_client import FakeRakutenClient
from marketplace.rakuten_settings import RakutenConfig
from marketplace.yahoo_auction_client import FakeYahooAuctionClient
from marketplace.yahoo_auction_settings import YahooAuctionConfig
from marketplace.yahoo_settings import YahooApiSettings
from marketplace.vestiaire_client import FakeVestiaireClient
from marketplace.vestiaire_exceptions import VestiaireConfigurationError
from marketplace.vestiaire_marketplace import create_vestiaire_marketplace
from marketplace.vestiaire_settings import VestiaireSettings
from marketplace.fashionphile_client import FakeFashionphileClient
from marketplace.fashionphile_exceptions import FashionphileConfigurationError
from marketplace.fashionphile_marketplace import create_fashionphile_marketplace
from marketplace.fashionphile_settings import FashionphileSettings
from marketplace.therealreal_client import FakeTheRealRealClient
from marketplace.therealreal_exceptions import TheRealRealConfigurationError
from marketplace.therealreal_marketplace import create_therealreal_marketplace
from marketplace.therealreal_settings import TheRealRealSettings
from used_luxury.demo_marketplace import create_used_luxury_demo_marketplace
from used_luxury.demo_provider import FakeUsedLuxuryProvider
from models.marketplace_listing import MarketplaceListing
from models.product import Product
from price_compare.marketplace_profit_service import calculate_profit_from_search_results
from price_compare.price_comparator import PriceSelectionStrategy
from price_compare.profit_calculator import ProfitCalculator
from price_compare.profit_config import ProfitConfig
from price_compare.ranking_engine import RankingEngine, RankingSortKey

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent / "tests" / "fixtures"


def build_sample_products() -> list[Product]:
    """
    Build sample products for foundation verification.

    Returns:
        In-memory product list without network access.
    """
    products = [
        Product(
            name="Sample Tote Bag",
            brand="Demo Brand",
            price=500.0,
            currency="USD",
            exchange_rate=DEFAULT_EXCHANGE_RATE,
            store_name="Foundation",
            country="US",
            yahoo_price=95000.0,
        ),
        Product(
            name="Sample Loafers",
            brand="Demo Brand",
            price=300.0,
            currency="USD",
            exchange_rate=DEFAULT_EXCHANGE_RATE,
            store_name="Foundation",
            country="US",
            rakuten_price=52000.0,
        ),
    ]

    for product in products:
        product.calculate_landed_cost()
        product.calculate_profit()

    return products


def build_phase2_products() -> list[Product]:
    """
    Build local Phase 2 sample products without network access.

    Returns:
        Sample overseas products with domestic price candidates.
    """
    return build_phase3_products()


def build_phase3_products() -> list[Product]:
    """
    Build local Phase 3 sample products.

    Returns:
        Sample overseas products for domestic marketplace matching.
    """
    return [
        Product(
            name="Phase3 Sale Bag",
            brand="Gucci",
            model="GG-MARMONT",
            price=600.0,
            original_price=750.0,
            sale_price=600.0,
            currency="USD",
            exchange_rate=150.0,
            store_name="Cettire",
            country="US",
            sku="P3-001",
            url="https://example.com/products/phase3-sale-bag",
            image_url="https://example.com/images/phase3-sale-bag.jpg",
        ),
        Product(
            name="Phase3 Regular Shoes",
            brand="Prada",
            model="PRD-LOAFER",
            price=400.0,
            original_price=400.0,
            currency="EUR",
            exchange_rate=165.0,
            store_name="Baltini",
            country="IT",
            sku="P3-002",
            url="https://example.com/products/phase3-shoes",
        ),
        Product(
            name="Phase3 Loss Item",
            brand="Demo Brand",
            price=900.0,
            currency="USD",
            exchange_rate=150.0,
            store_name="Italist",
            country="IT",
            sku="P3-003",
        ),
    ]


def build_phase3_listings() -> dict[str, list[MarketplaceListing]]:
    """
    Build injected domestic listing candidates for local marketplace.

    Returns:
        Mapping from product SKU to listing candidates.
    """
    return {
        "P3-001": [
            MarketplaceListing(
                marketplace_name="local-yahoo",
                listing_id="Y-100",
                title="Gucci Marmont Bag",
                brand="Gucci",
                model_number="GG-MARMONT",
                sku="P3-001",
                jan_code="4901234567890",
                price_jpy=Decimal("98000"),
                shipping_jpy=Decimal("500"),
                listing_url="https://example.com/domestic/yahoo/bag",
                image_url="https://example.com/domestic/yahoo/bag.jpg",
                seller_rating=Decimal("4.5"),
                sold_count=12,
            ),
            MarketplaceListing(
                marketplace_name="local-rakuten",
                listing_id="R-200",
                title="Gucci Bag",
                brand="Gucci",
                price_jpy=Decimal("102000"),
                shipping_jpy=Decimal("0"),
                listing_url="https://example.com/domestic/rakuten/bag",
            ),
            MarketplaceListing(
                marketplace_name="local-invalid",
                listing_id="BAD-1",
                title="",
                price_jpy=Decimal("1000"),
                listing_url="https://example.com/domestic/invalid",
            ),
        ],
        "P3-002": [
            MarketplaceListing(
                marketplace_name="local-mercari",
                listing_id="M-300",
                title="Prada Loafer Shoes",
                brand="Prada",
                model_number="PRD-LOAFER",
                sku="P3-002",
                price_jpy=Decimal("72000"),
                shipping_jpy=Decimal("700"),
                listing_url="https://example.com/domestic/mercari/shoes",
            ),
        ],
        "P3-003": [],
    }


def resolve_marketplace_name(argv: list[str] | None = None) -> str:
    """
    Resolve marketplace name from CLI args or environment.

    Args:
        argv: Optional argument list override for testing.

    Returns:
        Marketplace identifier (defaults to local).
    """
    args = argv if argv is not None else sys.argv[1:]
    for index, arg in enumerate(args):
        if arg == "--marketplace" and index + 1 < len(args):
            return args[index + 1].strip().lower()
    if RAKUTEN_API_ENABLED and (RAKUTEN_API_DEMO_ENABLED or "--demo-rakuten" in args):
        return "rakuten"
    if YAHOO_AUCTION_ENABLED and (
        YAHOO_AUCTION_DEMO_ENABLED or "--demo-yahoo-auction" in args
    ):
        return "yahoo_auction"
    if USED_LUXURY_DEMO_ENABLED or "--demo-used-luxury" in args:
        return "used_demo"
    if VESTIAIRE_DEMO_ENABLED or "--demo-vestiaire" in args:
        return "vestiaire"
    if FASHIONPHILE_DEMO_ENABLED or "--demo-fashionphile" in args:
        return "fashionphile"
    if THEREALREAL_DEMO_ENABLED or "--demo-therealreal" in args:
        return "therealreal"
    if AMAZON_JP_ENABLED and (AMAZON_JP_DEMO_ENABLED or "--demo-amazon" in args):
        return "amazon_jp"
    if YAHOO_API_ENABLED:
        return "yahoo"
    return "local"


def is_vestiaire_demo_requested(argv: list[str] | None = None) -> bool:
    """Return True when Vestiaire demo mode is explicitly requested."""
    args = argv if argv is not None else sys.argv[1:]
    return VESTIAIRE_DEMO_ENABLED or "--demo-vestiaire" in args


def build_vestiaire_demo_client() -> FakeVestiaireClient | None:
    """
    Build a fake Vestiaire client from local fixture JSON.

    Returns:
        FakeVestiaireClient when demo fixture exists, otherwise None.
    """
    settings = VestiaireSettings.from_env()
    fixture_path = FIXTURES_DIR / settings.demo_fixture_path
    if not fixture_path.exists():
        logger.warning("Vestiaire demo fixture not found: %s", fixture_path)
        return None
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    page_2 = FIXTURES_DIR / "vestiaire_search_page_2.json"
    if page_2.exists():
        return FakeVestiaireClient(
            pages={
                1: payload,
                2: json.loads(page_2.read_text(encoding="utf-8")),
            }
        )
    return FakeVestiaireClient(payload)


def is_fashionphile_demo_requested(argv: list[str] | None = None) -> bool:
    """Return True when Fashionphile demo mode is explicitly requested."""
    args = argv if argv is not None else sys.argv[1:]
    return FASHIONPHILE_DEMO_ENABLED or "--demo-fashionphile" in args


def build_fashionphile_demo_client() -> FakeFashionphileClient | None:
    """
    Build a fake Fashionphile client from local fixture JSON.

    Returns:
        FakeFashionphileClient when demo fixture exists, otherwise None.
    """
    settings = FashionphileSettings.from_env()
    fixture_path = FIXTURES_DIR / settings.demo_fixture_path
    if not fixture_path.exists():
        logger.warning("Fashionphile demo fixture not found: %s", fixture_path)
        return None
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    page_2 = FIXTURES_DIR / "fashionphile_search_page_2.json"
    if page_2.exists():
        return FakeFashionphileClient(
            pages={
                1: payload,
                2: json.loads(page_2.read_text(encoding="utf-8")),
            }
        )
    return FakeFashionphileClient(payload)


def is_therealreal_demo_requested(argv: list[str] | None = None) -> bool:
    """Return True when The RealReal demo mode is explicitly requested."""
    args = argv if argv is not None else sys.argv[1:]
    return THEREALREAL_DEMO_ENABLED or "--demo-therealreal" in args


def build_therealreal_demo_client() -> FakeTheRealRealClient | None:
    """Build a fake The RealReal client from local fixture JSON."""
    settings = TheRealRealSettings.from_env()
    fixture_path = FIXTURES_DIR / settings.demo_fixture_path
    if not fixture_path.exists():
        logger.warning("The RealReal demo fixture not found: %s", fixture_path)
        return None
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    page_2 = FIXTURES_DIR / "therealreal_search_page_2.json"
    if page_2.exists():
        return FakeTheRealRealClient(
            pages={
                1: payload,
                2: json.loads(page_2.read_text(encoding="utf-8")),
            }
        )
    return FakeTheRealRealClient(payload)


def is_used_luxury_demo_requested(argv: list[str] | None = None) -> bool:
    """Return True when used luxury demo mode is explicitly requested."""
    args = argv if argv is not None else sys.argv[1:]
    return USED_LUXURY_DEMO_ENABLED or "--demo-used-luxury" in args


def build_used_luxury_demo_provider() -> FakeUsedLuxuryProvider | None:
    """
    Build a fake used luxury provider from local fixture JSON.

    Returns:
        FakeUsedLuxuryProvider when demo fixture exists, otherwise None.
    """
    fixture_path = FIXTURES_DIR / "used_luxury_normal.json"
    if not fixture_path.exists():
        logger.warning("Used luxury demo fixture not found: %s", fixture_path)
        return None
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return FakeUsedLuxuryProvider(payload)


def is_yahoo_auction_demo_requested(argv: list[str] | None = None) -> bool:
    """Return True when Yahoo Auction demo mode is explicitly requested."""
    args = argv if argv is not None else sys.argv[1:]
    return YAHOO_AUCTION_DEMO_ENABLED or "--demo-yahoo-auction" in args


def build_yahoo_auction_demo_client() -> FakeYahooAuctionClient | None:
    """
    Build a fake Yahoo Auction client from local fixture JSON.

    Returns:
        FakeYahooAuctionClient when demo fixture exists, otherwise None.
    """
    fixture_path = FIXTURES_DIR / "yahoo_auction_search_normal.json"
    if not fixture_path.exists():
        logger.warning("Yahoo Auction demo fixture not found: %s", fixture_path)
        return None
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return FakeYahooAuctionClient(payload)


def is_rakuten_demo_requested(argv: list[str] | None = None) -> bool:
    """Return True when Rakuten demo mode is explicitly requested."""
    args = argv if argv is not None else sys.argv[1:]
    return RAKUTEN_API_DEMO_ENABLED or "--demo-rakuten" in args


def build_rakuten_demo_client() -> FakeRakutenClient | None:
    """
    Build a fake Rakuten client from local fixture JSON.

    Returns:
        FakeRakutenClient when demo fixture exists, otherwise None.
    """
    fixture_path = FIXTURES_DIR / "rakuten_search_normal.json"
    if not fixture_path.exists():
        logger.warning("Rakuten demo fixture not found: %s", fixture_path)
        return None
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return FakeRakutenClient(payload)


def is_amazon_demo_requested(argv: list[str] | None = None) -> bool:
    """Return True when Amazon demo mode is explicitly requested."""
    args = argv if argv is not None else sys.argv[1:]
    return AMAZON_JP_DEMO_ENABLED or "--demo-amazon" in args


def build_amazon_demo_client() -> FakeAmazonClient | None:
    """
    Build a fake Amazon client from local fixture JSON.

    Returns:
        FakeAmazonClient when demo fixture exists, otherwise None.
    """
    fixture_path = FIXTURES_DIR / "amazon_search_normal.json"
    if not fixture_path.exists():
        logger.warning("Amazon demo fixture not found: %s", fixture_path)
        return None
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return FakeAmazonClient(payload)


def _normalize_selected_marketplace(selected: str) -> str:
    """Normalize CLI marketplace aliases to canonical names."""
    normalized = selected.strip().lower()
    if normalized in {"yahoo_auction", "yahoo-auction", "yahooauction", "auctions"}:
        return "yahoo_auction"
    if normalized in {"used_demo", "used-luxury", "usedluxury"}:
        return "used_demo"
    if normalized in {"vestiaire", "vestiaire_collective", "vestiaire-collective", "vc"}:
        return "vestiaire"
    if normalized in {"fashionphile", "fashion_phile", "fashion-phile", "fp"}:
        return "fashionphile"
    if normalized in {"therealreal", "the_real_real", "the-real-real", "realreal", "trr"}:
        return "therealreal"
    return normalized


def run_phase3(marketplace_name: str | None = None) -> Path:
    """
    Run the Phase 3/4 pipeline using local or Yahoo marketplace candidates.

    Args:
        marketplace_name: Optional marketplace override.

    Returns:
        Path to the generated Excel workbook.
    """
    selected = (marketplace_name or resolve_marketplace_name()).strip().lower()
    yahoo_settings = YahooApiSettings.from_env()
    amazon_settings = AmazonConfig.from_env()
    rakuten_settings = RakutenConfig.from_env()
    yahoo_auction_settings = YahooAuctionConfig.from_env()
    vestiaire_settings = VestiaireSettings.from_env()
    fashionphile_settings = FashionphileSettings.from_env()
    therealreal_settings = TheRealRealSettings.from_env()
    amazon_client = None
    rakuten_client = None
    yahoo_auction_client = None
    vestiaire_client = None
    fashionphile_client = None
    therealreal_client = None

    selected = _normalize_selected_marketplace(selected)

    if selected == "rakuten":
        if is_rakuten_demo_requested():
            rakuten_client = build_rakuten_demo_client()
            if rakuten_client is None:
                logger.warning("Rakuten demo client unavailable; falling back to local marketplace")
                selected = "local"
        else:
            logger.warning("Rakuten marketplace is not configured; skipping Rakuten search.")
            selected = "local"

    if selected in {"amazon_jp", "amazon"}:
        if is_amazon_demo_requested():
            amazon_client = build_amazon_demo_client()
            if amazon_client is None:
                logger.warning("Amazon demo client unavailable; falling back to local marketplace")
                selected = "local"
        else:
            logger.warning("Amazon marketplace is not configured; skipping Amazon search.")
            selected = "local"

    if selected == "yahoo_auction":
        if is_yahoo_auction_demo_requested():
            yahoo_auction_client = build_yahoo_auction_demo_client()
            if yahoo_auction_client is None:
                logger.warning(
                    "Yahoo Auction demo client unavailable; falling back to local marketplace"
                )
                selected = "local"
        elif not yahoo_auction_settings.has_live_data_source:
            logger.warning("Yahoo Auction live data source is not configured; skipping search.")

    if selected == "used_demo":
        if not is_used_luxury_demo_requested():
            logger.warning("Used luxury demo is not enabled; falling back to local marketplace")
            selected = "local"

    if selected == "vestiaire":
        if is_vestiaire_demo_requested():
            vestiaire_client = build_vestiaire_demo_client()
            if vestiaire_client is None:
                logger.warning("Vestiaire demo client unavailable; falling back to local marketplace")
                selected = "local"
        else:
            logger.error(
                "Vestiaire Collective live client is not implemented. "
                "Use --demo-vestiaire for fixture demo mode."
            )
            selected = "local"

    if selected == "fashionphile":
        if is_fashionphile_demo_requested():
            fashionphile_client = build_fashionphile_demo_client()
            if fashionphile_client is None:
                logger.warning(
                    "Fashionphile demo client unavailable; falling back to local marketplace"
                )
                selected = "local"
        else:
            logger.error(
                "Fashionphile live client is not implemented. "
                "Use --demo-fashionphile for fixture demo mode."
            )
            selected = "local"

    if selected == "therealreal":
        if is_therealreal_demo_requested():
            therealreal_client = build_therealreal_demo_client()
            if therealreal_client is None:
                logger.warning(
                    "The RealReal demo client unavailable; falling back to local marketplace"
                )
                selected = "local"
        else:
            logger.error(
                "The RealReal live client is not implemented. "
                "Use --demo-therealreal for fixture demo mode."
            )
            selected = "local"

    if selected == "yahoo" and not yahoo_settings.can_execute:
        logger.warning(
            "Yahoo API is enabled but Client ID is missing; falling back to local marketplace"
        )
        selected = "local"

    products = build_phase3_products()
    listings_map = build_phase3_listings() if selected == "local" else None

    if selected == "used_demo":
        provider = build_used_luxury_demo_provider()
        if provider is None:
            logger.warning("Used luxury demo provider unavailable; falling back to local marketplace")
            selected = "local"
        else:
            marketplace = create_used_luxury_demo_marketplace(provider=provider)
            calculator = ProfitCalculator(
                ProfitConfig(
                    international_shipping_jpy=Decimal("2500"),
                    customs_duty_rate=Decimal("0.08"),
                    import_tax_rate=Decimal("0.10"),
                    domestic_shipping_jpy=Decimal("800"),
                    marketplace_fee_rate=Decimal("0.12"),
                    other_costs_jpy=Decimal("500"),
                )
            )
            search_results = [marketplace.search(product) for product in products]
            all_listings = [listing for result in search_results for listing in result.listings]
            valid_count = sum(len(result.valid_listings) for result in search_results)
            results = calculate_profit_from_search_results(search_results, calculator)
            ranked = RankingEngine(calculator.config).rank(
                results,
                sort_key=RankingSortKey.PROFIT,
                descending=True,
            )
            exporter = ExcelExporter(output_dir=OUTPUT_DIR, filename=EXCEL_FILENAME)
            output_path = exporter.export_phase3_workbook(products, all_listings, ranked)
            logger.info(
                "Used luxury demo export completed: %s (products=%d, listings=%d, valid=%d, results=%d)",
                output_path,
                len(products),
                len(all_listings),
                valid_count,
                len(ranked),
            )
            return output_path

    if selected == "vestiaire" and vestiaire_client is not None:
        marketplace = create_vestiaire_marketplace(
            client=vestiaire_client,
            settings=vestiaire_settings,
        )
        calculator = ProfitCalculator(
            ProfitConfig(
                international_shipping_jpy=Decimal("2500"),
                customs_duty_rate=Decimal("0.08"),
                import_tax_rate=Decimal("0.10"),
                domestic_shipping_jpy=Decimal("800"),
                marketplace_fee_rate=Decimal("0.12"),
                other_costs_jpy=Decimal("500"),
            )
        )
        search_results = [marketplace.search(product) for product in products]
        all_listings = [listing for result in search_results for listing in result.listings]
        valid_count = sum(len(result.valid_listings) for result in search_results)
        results = calculate_profit_from_search_results(search_results, calculator)
        ranked = RankingEngine(calculator.config).rank(
            results,
            sort_key=RankingSortKey.PROFIT,
            descending=True,
        )
        exporter = ExcelExporter(output_dir=OUTPUT_DIR, filename=EXCEL_FILENAME)
        output_path = exporter.export_phase3_workbook(products, all_listings, ranked)
        logger.info(
            "Vestiaire demo export completed: %s (products=%d, listings=%d, valid=%d, results=%d)",
            output_path,
            len(products),
            len(all_listings),
            valid_count,
            len(ranked),
        )
        return output_path

    if selected == "fashionphile" and fashionphile_client is not None:
        marketplace = create_fashionphile_marketplace(
            client=fashionphile_client,
            settings=fashionphile_settings,
        )
        calculator = ProfitCalculator(
            ProfitConfig(
                international_shipping_jpy=Decimal("2500"),
                customs_duty_rate=Decimal("0.08"),
                import_tax_rate=Decimal("0.10"),
                domestic_shipping_jpy=Decimal("800"),
                marketplace_fee_rate=Decimal("0.12"),
                other_costs_jpy=Decimal("500"),
            )
        )
        search_results = [marketplace.search(product) for product in products]
        all_listings = [listing for result in search_results for listing in result.listings]
        valid_count = sum(len(result.valid_listings) for result in search_results)
        results = calculate_profit_from_search_results(search_results, calculator)
        ranked = RankingEngine(calculator.config).rank(
            results,
            sort_key=RankingSortKey.PROFIT,
            descending=True,
        )
        exporter = ExcelExporter(output_dir=OUTPUT_DIR, filename=EXCEL_FILENAME)
        output_path = exporter.export_phase3_workbook(products, all_listings, ranked)
        logger.info(
            "Fashionphile demo export completed: %s (products=%d, listings=%d, valid=%d, results=%d)",
            output_path,
            len(products),
            len(all_listings),
            valid_count,
            len(ranked),
        )
        return output_path

    if selected == "therealreal" and therealreal_client is not None:
        marketplace = create_therealreal_marketplace(
            client=therealreal_client,
            settings=therealreal_settings,
        )
        calculator = ProfitCalculator(
            ProfitConfig(
                international_shipping_jpy=Decimal("2500"),
                customs_duty_rate=Decimal("0.08"),
                import_tax_rate=Decimal("0.10"),
                domestic_shipping_jpy=Decimal("800"),
                marketplace_fee_rate=Decimal("0.12"),
                other_costs_jpy=Decimal("500"),
            )
        )
        search_results = [marketplace.search(product) for product in products]
        all_listings = [listing for result in search_results for listing in result.listings]
        valid_count = sum(len(result.valid_listings) for result in search_results)
        results = calculate_profit_from_search_results(search_results, calculator)
        ranked = RankingEngine(calculator.config).rank(
            results,
            sort_key=RankingSortKey.PROFIT,
            descending=True,
        )
        exporter = ExcelExporter(output_dir=OUTPUT_DIR, filename=EXCEL_FILENAME)
        output_path = exporter.export_phase3_workbook(products, all_listings, ranked)
        logger.info(
            "The RealReal demo export completed: %s (products=%d, listings=%d, valid=%d, results=%d)",
            output_path,
            len(products),
            len(all_listings),
            valid_count,
            len(ranked),
        )
        return output_path

    try:
        marketplace = create_marketplace(
            selected,
            listings_by_product_key=listings_map,
            selection_strategy=PriceSelectionStrategy.HIGHEST,
            yahoo_settings=yahoo_settings,
            amazon_settings=amazon_settings,
            amazon_client=amazon_client,
            rakuten_settings=rakuten_settings,
            rakuten_client=rakuten_client,
            yahoo_auction_settings=yahoo_auction_settings,
            yahoo_auction_client=yahoo_auction_client,
            vestiaire_settings=vestiaire_settings,
            vestiaire_client=vestiaire_client,
            fashionphile_settings=fashionphile_settings,
            fashionphile_client=fashionphile_client,
            therealreal_settings=therealreal_settings,
            therealreal_client=therealreal_client,
        )
    except (VestiaireConfigurationError, FashionphileConfigurationError, TheRealRealConfigurationError) as exc:
        logger.error("%s", exc)
        selected = "local"
        marketplace = create_marketplace(
            "local",
            listings_by_product_key=listings_map,
            selection_strategy=PriceSelectionStrategy.HIGHEST,
        )
    calculator = ProfitCalculator(
        ProfitConfig(
            international_shipping_jpy=Decimal("2500"),
            customs_duty_rate=Decimal("0.08"),
            import_tax_rate=Decimal("0.10"),
            domestic_shipping_jpy=Decimal("800"),
            marketplace_fee_rate=Decimal("0.12"),
            other_costs_jpy=Decimal("500"),
        )
    )

    search_results = [marketplace.search(product) for product in products]
    all_listings = [listing for result in search_results for listing in result.listings]
    valid_count = sum(len(result.valid_listings) for result in search_results)

    results = calculate_profit_from_search_results(search_results, calculator)
    ranked = RankingEngine(calculator.config).rank(
        results,
        sort_key=RankingSortKey.PROFIT,
        descending=True,
    )

    exporter = ExcelExporter(output_dir=OUTPUT_DIR, filename=EXCEL_FILENAME)
    output_path = exporter.export_phase3_workbook(products, all_listings, ranked)

    logger.info(
        "Phase 3 export completed: %s (marketplace=%s, products=%d, listings=%d, valid=%d, results=%d)",
        output_path,
        selected,
        len(products),
        len(all_listings),
        valid_count,
        len(ranked),
    )
    return output_path


def run_phase2() -> Path:
    """Backward-compatible alias for Phase 3 pipeline."""
    return run_phase3()


def run(marketplace_name: str | None = None) -> Path:
    """
    Run the application pipeline and export Excel.

    Args:
        marketplace_name: Optional marketplace override.

    Returns:
        Path to the generated Excel file.
    """
    logger.info(
        "Starting Phase 3 pipeline with %d sample products (marketplace=%s)",
        len(build_phase3_products()),
        marketplace_name or resolve_marketplace_name(),
    )
    return run_phase3(marketplace_name=marketplace_name)


def main() -> None:
    """CLI entry point."""
    setup_logging()
    logger.info("BrandProfitFinder Phase 3/4/5A/6/7/8/9/10/11 started")
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        output_path = run()
    logger.info("BrandProfitFinder Phase 3/4/5A/6/7/8/9/10/11 finished: %s", output_path)


if __name__ == "__main__":
    main()
