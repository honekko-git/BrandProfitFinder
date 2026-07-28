"""Unit tests for scanner.scanner_factory."""

import pytest

from scanner.base_scanner import BaseScanner
from scanner.baltini import BaltiniScanner
from scanner.cettire import CettireScanner
from scanner.italist import ItalistScanner
from scanner.scanner_factory import create_scanner, get_all_scanners


def test_create_scanner_cettire() -> None:
    scanner = create_scanner("Cettire")
    assert isinstance(scanner, CettireScanner)
    assert isinstance(scanner, BaseScanner)
    assert scanner.store_name == "Cettire"


def test_create_scanner_baltini() -> None:
    scanner = create_scanner("baltini")
    assert isinstance(scanner, BaltiniScanner)
    assert scanner.store_name == "Baltini"


def test_create_scanner_italist() -> None:
    scanner = create_scanner("italist")
    assert isinstance(scanner, ItalistScanner)
    assert scanner.store_name == "Italist"


def test_create_scanner_case_insensitive() -> None:
    scanner = create_scanner("  CETTIRE  ")
    assert isinstance(scanner, CettireScanner)


def test_create_scanner_italist_normalization() -> None:
    scanner = create_scanner("  ITALIST  ")
    assert isinstance(scanner, ItalistScanner)


def test_create_scanner_unsupported_store() -> None:
    with pytest.raises(ValueError, match="Unsupported store"):
        create_scanner("UnknownStore")


def test_get_all_scanners_returns_implemented_stores() -> None:
    scanners = get_all_scanners()
    assert len(scanners) == 3
    store_names = {scanner.store_name for scanner in scanners}
    assert store_names == {"Cettire", "Baltini", "Italist"}
