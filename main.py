"""
BrandProfitFinder application entry point.

Phase 3: domestic marketplace candidates, profit calculation, and Excel export.
No external site access is performed.
"""

import logging
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from config.logging_config import setup_logging
from config.settings import DEFAULT_EXCHANGE_RATE, EXCEL_FILENAME, OUTPUT_DIR
from excel.exporter import ExcelExporter
from marketplace.local_marketplace import LocalMarketplace
from marketplace.marketplace_factory import create_marketplace
from models.marketplace_listing import MarketplaceListing
from models.product import Product
from price_compare.marketplace_profit_service import calculate_profit_from_search_results
from price_compare.price_comparator import PriceComparator, PriceSelectionStrategy
from price_compare.profit_calculator import ProfitCalculator
from price_compare.profit_config import ProfitConfig
from price_compare.ranking_engine import RankingEngine, RankingSortKey

logger = logging.getLogger(__name__)


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


def run_phase3() -> Path:
    """
    Run the Phase 3 pipeline using local marketplace candidates.

    Returns:
        Path to the generated Excel workbook.
    """
    products = build_phase3_products()
    listings_map = build_phase3_listings()
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
        "Phase 3 export completed: %s (products=%d, listings=%d, valid=%d, results=%d)",
        output_path,
        len(products),
        len(all_listings),
        valid_count,
        len(ranked),
    )
    return output_path


def run_phase2() -> Path:
    """Backward-compatible alias for Phase 3 pipeline."""
    return run_phase3()


def run() -> Path:
    """
    Run the application pipeline and export Excel.

    Returns:
        Path to the generated Excel file.
    """
    logger.info("Starting Phase 3 pipeline with %d sample products", len(build_phase3_products()))
    return run_phase3()


def main() -> None:
    """CLI entry point."""
    setup_logging()
    logger.info("BrandProfitFinder Phase 3 started")
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        output_path = run()
    logger.info("BrandProfitFinder Phase 3 finished: %s", output_path)


if __name__ == "__main__":
    main()
