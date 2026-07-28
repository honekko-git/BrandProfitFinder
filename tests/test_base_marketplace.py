"""Unit tests for marketplace.base_marketplace."""

import pytest

from marketplace.base_marketplace import BaseMarketplace
from marketplace.local_marketplace import LocalMarketplace


def test_base_marketplace_is_abstract() -> None:
    with pytest.raises(TypeError):
        BaseMarketplace()  # type: ignore[abstract]


def test_local_is_base_marketplace() -> None:
    marketplace = LocalMarketplace()
    assert isinstance(marketplace, BaseMarketplace)
