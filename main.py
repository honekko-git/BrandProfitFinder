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
    if AMAZON_JP_ENABLED and (AMAZON_JP_DEMO_ENABLED or "--demo-amazon" in args):
        return "amazon_jp"
    if YAHOO_API_ENABLED:
        return "yahoo"
    return "local"


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
    amazon_client = None
    rakuten_client = None
    yahoo_auction_client = None

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

    if selected == "yahoo" and not yahoo_settings.can_execute:
        logger.warning(
            "Yahoo API is enabled but Client ID is missing; falling back to local marketplace"
        )
        selected = "local"

    products = build_phase3_products()
    listings_map = build_phase3_listings() if selected == "local" else None
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
    logger.info("BrandProfitFinder Phase 3/4/5A/6/7 started")
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        output_path = run()
    logger.info("BrandProfitFinder Phase 3/4/5A/6/7 finished: %s", output_path)


if __name__ == "__main__":
    main()
