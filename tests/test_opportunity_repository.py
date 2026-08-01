"""Tests for opportunity repository CRUD."""

from __future__ import annotations

from datetime import UTC, datetime

from app.storage.models import OpportunityRecord, OpportunityStatus
from app.storage.repository import OpportunityRepository


def _record(name: str) -> OpportunityRecord:
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    return OpportunityRecord(
        id=None,
        product_name=name,
        brand="Chanel",
        category="wallet",
        purchase_source="Fashionphile",
        purchase_url=f"https://example.invalid/{name}",
        purchase_price=100000.0,
        selling_market="Mercari",
        selling_url=f"https://example.invalid/mercari/{name}",
        selling_price=150000.0,
        estimated_profit=30000.0,
        profit_margin=25.0,
        demand_score=80.0,
        turnover_score=70.0,
        arbitrage_score=75.0,
        decision="BUY",
        status=OpportunityStatus.NEW,
        created_at=now,
        updated_at=now,
    )


def test_opportunity_repository_crud(tmp_path) -> None:
    repository = OpportunityRepository(tmp_path / "brand_profit.db")

    first = repository.save(_record("item-a"))
    second = repository.save(_record("item-b"))

    all_items = repository.list_all()
    assert len(all_items) == 2
    assert {item.product_name for item in all_items} == {"item-a", "item-b"}

    updated = repository.update_status(first.id, OpportunityStatus.PURCHASED)
    assert updated is not None
    assert updated.status is OpportunityStatus.PURCHASED

    assert repository.delete(second.id) is True
    assert repository.get_by_id(second.id) is None
    assert len(repository.list_all()) == 1


def test_opportunity_repository_find_by_purchase_url(tmp_path) -> None:
    repository = OpportunityRepository(tmp_path / "brand_profit.db")
    saved = repository.save(_record("lookup-item"))

    found = repository.find_by_purchase_url(saved.purchase_url)

    assert found is not None
    assert found.id == saved.id
