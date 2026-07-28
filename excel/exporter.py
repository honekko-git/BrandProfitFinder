"""
Excel export for product reports.
"""

import logging
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from config.constants import (
    SHEET_DOMESTIC_LISTINGS,
    SHEET_MARKETPLACE_COMPARISON,
    SHEET_PROFIT_RANKING,
    SHEET_ROI_RANKING,
)
from config.settings import EXCEL_FILENAME, OUTPUT_DIR
from comparison.formatter import comparison_result_to_dict
from comparison.models import ProductComparisonResult
from excel.formatter import apply_listing_formatting, apply_price_result_formatting, apply_sheet_layout
from excel.template import (
    MARKETPLACE_COMPARISON_COLUMNS,
    MARKETPLACE_LISTING_COLUMNS,
    PRICE_RESULT_COLUMNS,
    PRODUCT_COLUMNS,
    price_result_columns,
)
from models.marketplace_listing import MarketplaceListing
from models.price_result import PriceResult
from models.product import Product

logger = logging.getLogger(__name__)

SHEET_PRICE_RESULTS = "Profit Analysis"


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
        self._format_product_sheet(output_path)
        logger.info("Exported %d products to %s", len(products), output_path)
        return output_path

    def export_price_results(self, results: list[PriceResult]) -> Path:
        """
        Export profit calculation results to Excel.

        Args:
            results: Calculated price results.

        Returns:
            Path to the generated file.
        """
        rows = [result.to_dict() for result in results]
        result_columns = price_result_columns(results)
        dataframe = pd.DataFrame(rows, columns=result_columns)
        output_path = self.output_path
        dataframe.to_excel(output_path, index=False, sheet_name=SHEET_PRICE_RESULTS)
        self._format_price_result_sheet(output_path, len(results), result_columns)
        logger.info("Exported %d price results to %s", len(results), output_path)
        return output_path

    def export_phase3_workbook(
        self,
        products: list[Product],
        listings: list[MarketplaceListing],
        results: list[PriceResult],
        comparison_results: list[ProductComparisonResult] | None = None,
    ) -> Path:
        """
        Export products, domestic listings, and profit results.

        Args:
            products: Product list for backward-compatible export.
            listings: Domestic marketplace listing candidates.
            results: Profit calculation results.
            comparison_results: Optional cross-marketplace comparison rows.

        Returns:
            Path to the generated workbook.
        """
        product_rows = [product.to_dict() for product in products]
        listing_rows = [listing.to_dict() for listing in listings]
        result_rows = [result.to_dict() for result in results]
        result_columns = price_result_columns(results)
        comparison_rows = (
            [comparison_result_to_dict(item) for item in comparison_results]
            if comparison_results
            else None
        )
        output_path = self.output_path

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            pd.DataFrame(product_rows, columns=PRODUCT_COLUMNS).to_excel(
                writer,
                index=False,
                sheet_name=SHEET_PROFIT_RANKING,
            )
            pd.DataFrame(listing_rows, columns=MARKETPLACE_LISTING_COLUMNS).to_excel(
                writer,
                index=False,
                sheet_name=SHEET_DOMESTIC_LISTINGS,
            )
            pd.DataFrame(result_rows, columns=result_columns).to_excel(
                writer,
                index=False,
                sheet_name=SHEET_PRICE_RESULTS,
            )
            pd.DataFrame(
                [
                    {
                        "rank": index,
                        "label": result.product.name if result.product else "",
                        "score": float(result.ranking_score),
                    }
                    for index, result in enumerate(results, start=1)
                ],
                columns=["rank", "label", "score"],
            ).to_excel(writer, index=False, sheet_name=SHEET_ROI_RANKING)
            if comparison_rows is not None:
                pd.DataFrame(comparison_rows, columns=MARKETPLACE_COMPARISON_COLUMNS).to_excel(
                    writer,
                    index=False,
                    sheet_name=SHEET_MARKETPLACE_COMPARISON,
                )

        workbook = load_workbook(output_path)
        if SHEET_PROFIT_RANKING in workbook.sheetnames:
            apply_sheet_layout(workbook[SHEET_PROFIT_RANKING], len(PRODUCT_COLUMNS))
        if SHEET_DOMESTIC_LISTINGS in workbook.sheetnames:
            sheet = workbook[SHEET_DOMESTIC_LISTINGS]
            apply_sheet_layout(sheet, len(MARKETPLACE_LISTING_COLUMNS))
            apply_listing_formatting(sheet, MARKETPLACE_LISTING_COLUMNS, len(listings))
        if SHEET_PRICE_RESULTS in workbook.sheetnames:
            sheet = workbook[SHEET_PRICE_RESULTS]
            apply_sheet_layout(sheet, len(result_columns))
            apply_price_result_formatting(sheet, result_columns, len(results))
        if SHEET_ROI_RANKING in workbook.sheetnames:
            apply_sheet_layout(workbook[SHEET_ROI_RANKING], 3)
        if comparison_rows is not None and SHEET_MARKETPLACE_COMPARISON in workbook.sheetnames:
            apply_sheet_layout(
                workbook[SHEET_MARKETPLACE_COMPARISON],
                len(MARKETPLACE_COMPARISON_COLUMNS),
            )
        workbook.save(output_path)

        logger.info(
            "Exported Phase 3 workbook with %d products, %d listings, %d results%s to %s",
            len(products),
            len(listings),
            len(results),
            f", {len(comparison_rows)} comparisons" if comparison_rows is not None else "",
            output_path,
        )
        return output_path

    def export_phase2_workbook(
        self,
        products: list[Product],
        results: list[PriceResult],
    ) -> Path:
        """
        Export both legacy products and Phase 2 profit results.

        Args:
            products: Product list for backward-compatible export.
            results: Profit calculation results.

        Returns:
            Path to the generated workbook.
        """
        product_rows = [product.to_dict() for product in products]
        result_rows = [result.to_dict() for result in results]
        result_columns = price_result_columns(results)
        output_path = self.output_path

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            pd.DataFrame(product_rows, columns=PRODUCT_COLUMNS).to_excel(
                writer,
                index=False,
                sheet_name=SHEET_PROFIT_RANKING,
            )
            pd.DataFrame(result_rows, columns=result_columns).to_excel(
                writer,
                index=False,
                sheet_name=SHEET_PRICE_RESULTS,
            )
            pd.DataFrame(
                [
                    {
                        "rank": index,
                        "label": result.product.name if result.product else "",
                        "score": float(result.ranking_score),
                    }
                    for index, result in enumerate(results, start=1)
                ],
                columns=["rank", "label", "score"],
            ).to_excel(writer, index=False, sheet_name=SHEET_ROI_RANKING)

        workbook = load_workbook(output_path)
        if SHEET_PROFIT_RANKING in workbook.sheetnames:
            apply_sheet_layout(workbook[SHEET_PROFIT_RANKING], len(PRODUCT_COLUMNS))
        if SHEET_PRICE_RESULTS in workbook.sheetnames:
            sheet = workbook[SHEET_PRICE_RESULTS]
            apply_sheet_layout(sheet, len(result_columns))
            apply_price_result_formatting(sheet, result_columns, len(results))
        if SHEET_ROI_RANKING in workbook.sheetnames:
            apply_sheet_layout(workbook[SHEET_ROI_RANKING], 3)
        workbook.save(output_path)

        logger.info(
            "Exported Phase 2 workbook with %d products and %d results to %s",
            len(products),
            len(results),
            output_path,
        )
        return output_path

    def _format_product_sheet(self, output_path: Path) -> None:
        workbook = load_workbook(output_path)
        sheet = workbook.active
        apply_sheet_layout(sheet, len(PRODUCT_COLUMNS))
        workbook.save(output_path)

    def _format_price_result_sheet(
        self,
        output_path: Path,
        row_count: int,
        columns: list[str] | None = None,
    ) -> None:
        workbook = load_workbook(output_path)
        sheet = workbook.active
        column_list = columns or list(PRICE_RESULT_COLUMNS)
        apply_sheet_layout(sheet, len(column_list))
        apply_price_result_formatting(sheet, column_list, row_count)
        workbook.save(output_path)
