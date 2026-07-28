"""Foundation tests for main entry point (no real network)."""

from pathlib import Path

from main import build_sample_products, run


def test_build_sample_products_has_expected_values() -> None:
    products = build_sample_products()
    assert len(products) == 2
    assert all(product.landed_cost > 0 for product in products)
    assert all(product.profit != 0 or product.best_japanese_price() is None for product in products)


def test_run_exports_excel(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "foundation_run.xlsx")

    output_path = run()
    assert output_path.exists()
    assert output_path.name == "foundation_run.xlsx"
