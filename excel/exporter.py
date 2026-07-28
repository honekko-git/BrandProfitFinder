"""
Excel export for product reports.
"""

import logging
from pathlib import Path

import pandas as pd

from config.constants import SHEET_PROFIT_RANKING
from config.settings import EXCEL_FILENAME, OUTPUT_DIR
from excel.template import PRODUCT_COLUMNS
from models.product import Product

logger = logging.getLogger(__name__)


class ExcelExporter:
    """Generate Excel reports from product data."""

    def __init__(self, output_dir: Path | None = None, filename: str | None = None) -> None:
        """
        Initialize exporter with output location.

        Args:
            output_dir: Directory for generated files.
            filename: Output Excel filename.
        """
        self.output_dir = output_dir or OUTPUT_DIR
        self.filename = filename or EXCEL_FILENAME
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def output_path(self) -> Path:
        """Return full path to the output Excel file."""
        return self.output_dir / self.filename

    def export_products(self, products: list[Product]) -> Path:
        """
        Export products to a single-sheet Excel workbook.

        Args:
            products: Products to export.

        Returns:
            Path to the generated file.
        """
        rows = [product.to_dict() for product in products]
        dataframe = pd.DataFrame(rows, columns=PRODUCT_COLUMNS)
        output_path = self.output_path
        dataframe.to_excel(output_path, index=False, sheet_name=SHEET_PROFIT_RANKING)
        logger.info("Exported %d products to %s", len(products), output_path)
        return output_path
