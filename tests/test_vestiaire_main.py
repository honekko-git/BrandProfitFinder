"""Tests for Vestiaire main.py demo integration."""

from pathlib import Path
from unittest.mock import patch

import pytest

from main import (
    build_vestiaire_demo_client,
    is_vestiaire_demo_requested,
    resolve_marketplace_name,
    run_phase3,
)
from marketplace.vestiaire_exceptions import VestiaireConfigurationError
from marketplace.marketplace_factory import create_marketplace
from marketplace.vestiaire_settings import VestiaireSettings


def test_demo_cli_flag() -> None:
    assert is_vestiaire_demo_requested(["--demo-vestiaire"]) is True


def test_resolve_marketplace_vestiaire() -> None:
    assert resolve_marketplace_name(["--demo-vestiaire"]) == "vestiaire"


def test_demo_client_fixture() -> None:
    client = build_vestiaire_demo_client()
    assert client is not None


def test_demo_run_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "vestiaire_demo.xlsx")
    monkeypatch.setattr("main.VESTIAIRE_DEMO_ENABLED", True)
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)

    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        output_path = run_phase3(marketplace_name="vestiaire")

    assert output_path.exists()


def test_vestiaire_without_demo_falls_back(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "vestiaire_skip.xlsx")
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    monkeypatch.setattr("main.VESTIAIRE_DEMO_ENABLED", False)

    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        output_path = run_phase3(marketplace_name="vestiaire")

    assert output_path.exists()


def test_factory_config_error_without_client() -> None:
    with pytest.raises(VestiaireConfigurationError):
        create_marketplace("vestiaire", vestiaire_settings=VestiaireSettings.from_env())


def test_default_run_no_vestiaire_fixture(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "local.xlsx")
    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    monkeypatch.setattr("main.VESTIAIRE_DEMO_ENABLED", False)

    with patch("utils.http.fetch_url"), patch("utils.http.HttpClient"):
        output_path = run_phase3()

    assert output_path.exists()
    assert resolve_marketplace_name([]) == "local"
