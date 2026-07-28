"""Foundation tests for excel.exporter."""

from pathlib import Path

import openpyxl

from excel.exporter import ExcelExporter
from models.product import Product


def test_export_products_creates_excel(tmp_path: Path) -> None:
    products = [
        Product(
            name="Sample Bag",
            brand="Demo Brand",
            price=500.0,
            currency="USD",
            exchange_rate=160.0,
            landed_cost=80000.0,
        )
    ]
    exporter = ExcelExporter(output_dir=tmp_path, filename="foundation.xlsx")
    output_path = exporter.export_products(products)

    assert output_path.exists()
    workbook = openpyxl.load_workbook(output_path)
    sheet = workbook.active
    assert sheet.cell(row=1, column=1).value == "name"
    assert sheet.cell(row=2, column=1).value == "Sample Bag"
