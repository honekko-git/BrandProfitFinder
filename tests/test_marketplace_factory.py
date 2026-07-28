"""Unit tests for marketplace.marketplace_factory."""

import pytest

from marketplace.base_marketplace import BaseMarketplace
from marketplace.local_marketplace import LocalMarketplace
from marketplace.marketplace_factory import create_marketplace, get_all_marketplaces


def test_create_local_marketplace() -> None:
    marketplace = create_marketplace("local")
    assert isinstance(marketplace, LocalMarketplace)
    assert isinstance(marketplace, BaseMarketplace)


def test_case_insensitive() -> None:
    marketplace = create_marketplace("LOCAL")
    assert isinstance(marketplace, LocalMarketplace)


def test_whitespace_normalization() -> None:
    marketplace = create_marketplace("  local  ")
    assert isinstance(marketplace, LocalMarketplace)


def test_unsupported_marketplace_error() -> None:
    with pytest.raises(ValueError, match="Unsupported marketplace"):
        create_marketplace("amazon")


@pytest.mark.parametrize(
    "name,message",
    [
        ("rakuten", "Rakuten marketplace is not yet implemented"),
        ("yahoo", "Yahoo marketplace is not yet implemented"),
        ("mercari", "Mercari marketplace is not yet implemented"),
    ],
)
def test_not_implemented_marketplaces(name: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        create_marketplace(name)


def test_get_all_marketplaces() -> None:
    marketplaces = get_all_marketplaces()
    assert len(marketplaces) == 1
    assert isinstance(marketplaces[0], LocalMarketplace)
