"""
BrandProfitFinder application entry point.

Foundation phase: initializes logging and exports in-memory sample data.
No external site access or store scraping is performed.
"""

import logging
from pathlib import Path

from config.logging_config import setup_logging
from config.settings import DEFAULT_EXCHANGE_RATE, EXCEL_FILENAME, OUTPUT_DIR
from excel.exporter import ExcelExporter
from models.product import Product

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


def run() -> Path:
    """
    Run the foundation pipeline: prepare products and export Excel.

    Returns:
        Path to the generated Excel file.
    """
    products = build_sample_products()
    exporter = ExcelExporter(output_dir=OUTPUT_DIR, filename=EXCEL_FILENAME)
    output_path = exporter.export_products(products)
    logger.info("Foundation export completed: %s", output_path)
    return output_path


def main() -> None:
    """CLI entry point."""
    setup_logging()
    logger.info("BrandProfitFinder foundation started")
    run()
    logger.info("BrandProfitFinder foundation finished")


if __name__ == "__main__":
    main()
