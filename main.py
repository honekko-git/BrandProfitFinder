"""
BrandProfitFinder application entry point.

Phase 2: profit calculation, ranking, and Excel export using local sample data.
No external site access is performed.
"""

import logging
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from config.logging_config import setup_logging
from config.settings import DEFAULT_EXCHANGE_RATE, EXCEL_FILENAME, OUTPUT_DIR
from excel.exporter import ExcelExporter
from models.product import Product
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
    return [
        Product(
            name="Phase2 Sale Bag",
            brand="Sample Brand",
            price=600.0,
            original_price=750.0,
            sale_price=600.0,
            currency="USD",
            exchange_rate=150.0,
            store_name="Cettire",
            country="US",
            sku="P2-001",
            url="https://example.com/products/phase2-sale-bag",
            image_url="https://example.com/images/phase2-sale-bag.jpg",
            yahoo_price=98000.0,
            rakuten_price=102000.0,
        ),
        Product(
            name="Phase2 Regular Shoes",
            brand="Sample Brand",
            price=400.0,
            original_price=400.0,
            currency="EUR",
            exchange_rate=165.0,
            store_name="Baltini",
            country="IT",
            sku="P2-002",
            url="https://example.com/products/phase2-shoes",
            mercari_price=70000.0,
        ),
        Product(
            name="Phase2 Loss Item",
            brand="Sample Brand",
            price=900.0,
            currency="USD",
            exchange_rate=150.0,
            store_name="Italist",
            country="IT",
            sku="P2-003",
            yahoo_price=50000.0,
        ),
    ]


def run_phase2() -> Path:
    """
    Run the Phase 2 pipeline using local sample data.

    Returns:
        Path to the generated Excel workbook.
    """
    products = build_phase2_products()
    comparator = PriceComparator()
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

    results = []
    for product in products:
        candidates = {
            "yahoo": product.yahoo_price,
            "rakuten": product.rakuten_price,
            "mercari": product.mercari_price,
            "ebay": product.ebay_price,
        }
        selected = comparator.select_from_mapping(
            candidates,
            strategy=PriceSelectionStrategy.HIGHEST,
        )
        domestic_market = selected[0] if selected else "manual"
        domestic_price = selected[1] if selected else None
        results.append(calculator.calculate(product, domestic_price, domestic_market))

    ranked = RankingEngine(calculator.config).rank(
        results,
        sort_key=RankingSortKey.PROFIT,
        descending=True,
    )

    exporter = ExcelExporter(output_dir=OUTPUT_DIR, filename=EXCEL_FILENAME)
    output_path = exporter.export_phase2_workbook(products, ranked)
    logger.info("Phase 2 export completed: %s (%d results)", output_path, len(ranked))
    return output_path


def run() -> Path:
    """
    Run the application pipeline and export Excel.

    Returns:
        Path to the generated Excel file.
    """
    logger.info("Starting Phase 2 pipeline with %d sample products", len(build_phase2_products()))
    return run_phase2()


def main() -> None:
    """CLI entry point."""
    setup_logging()
    logger.info("BrandProfitFinder Phase 2 started")
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        output_path = run()
    logger.info("BrandProfitFinder Phase 2 finished: %s", output_path)


if __name__ == "__main__":
    main()
