"""Tests for used luxury main.py demo integration."""

from pathlib import Path
from unittest.mock import patch

from main import (
    build_used_luxury_demo_provider,
    is_used_luxury_demo_requested,
    resolve_marketplace_name,
    run_phase3,
)


def test_demo_cli_flag() -> None:
    assert is_used_luxury_demo_requested(["--demo-used-luxury"]) is True


def test_resolve_marketplace_used_demo() -> None:
    assert resolve_marketplace_name(["--demo-used-luxury"]) == "used_demo"


def test_demo_provider_fixture() -> None:
    provider = build_used_luxury_demo_provider()
    assert provider is not None


def test_demo_run_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "used_demo.xlsx")
    monkeypatch.setattr("main.USED_LUXURY_DEMO_ENABLED", True)
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)

    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        output_path = run_phase3(marketplace_name="used_demo")

    assert output_path.exists()


def test_default_run_no_fixture(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "local_only.xlsx")
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    monkeypatch.setattr("main.USED_LUXURY_DEMO_ENABLED", False)

    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        output_path = run_phase3()

    assert output_path.exists()
    assert resolve_marketplace_name([]) == "local"
