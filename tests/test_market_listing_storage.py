"""Tests for imported market listing SQLite storage."""

from __future__ import annotations

from datetime import UTC, datetime

from app.storage.market_listing_models import MarketListingRecord
from app.storage.market_listing_repository import MarketListingRepository


def test_market_listing_repository_save_and_list(tmp_path) -> None:
    repository = MarketListingRepository(tmp_path / "brand_profit.db")
    saved = repository.save(
        MarketListingRecord(
            id=None,
            title="CHANEL Wallet",
            brand="Chanel",
            category="Wallet",
            condition="Used",
            price=50000.0,
            currency="JPY",
            market_name="Fashionphile",
            url="https://example.invalid/chanel-wallet",
            external_key="import-test-001",
            created_at=datetime(2026, 7, 30, tzinfo=UTC),
        )
    )

    assert saved.id is not None
    loaded = repository.get_by_id(saved.id)
    assert loaded is not None
    assert loaded.title == "CHANEL Wallet"
    assert loaded.brand == "Chanel"
    assert loaded.market_name == "Fashionphile"


def test_market_listing_repository_search_and_delete(tmp_path) -> None:
    repository = MarketListingRepository(tmp_path / "brand_profit.db")
    saved = repository.save(
        MarketListingRecord(
            id=None,
            title="Louis Vuitton Speedy",
            brand="Louis Vuitton",
            category="Bag",
            condition="Used",
            price=120000.0,
            currency="JPY",
            market_name="The RealReal",
            url="https://example.invalid/lv-speedy",
            external_key="import-test-002",
            created_at=datetime(2026, 7, 30, tzinfo=UTC),
        )
    )
    assert saved.id is not None

    matches = repository.search("Louis")
    assert len(matches) == 1
    assert repository.delete(saved.id) is True
    assert repository.get_by_id(saved.id) is None
