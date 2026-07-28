"""CLI tests for cross-marketplace comparison demo."""

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import main


def test_comparison_demo_flag_detected() -> None:
    assert main.is_comparison_demo_requested(["--comparison-demo"]) is True
    assert main.is_comparison_demo_requested(["--demo-comparison"]) is True


def test_cli_help_documents_comparison_demo() -> None:
    parser = main.build_cli_parser()
    buffer = StringIO()
    parser.print_help(file=buffer)
    help_text = buffer.getvalue()
    assert "--comparison-demo" in help_text
    assert "--demo-comparison" in help_text


def test_comparison_demo_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main, "EXCEL_FILENAME", "cmp_cli.xlsx")
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        with patch.object(sys, "argv", ["main.py", "--comparison-demo"]):
            main.main()
    assert (tmp_path / "cmp_cli.xlsx").exists()


def test_stockx_demo_regression(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(main, "EXCEL_FILENAME", "stockx_reg.xlsx")
    monkeypatch.setattr(main, "STOCKX_DEMO_ENABLED", True)
    monkeypatch.setattr(main, "YAHOO_API_ENABLED", False)
    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        assert main.run_phase3(marketplace_name="stockx").exists()
