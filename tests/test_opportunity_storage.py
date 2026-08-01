"""Tests for SQLite opportunity storage."""

from __future__ import annotations

from datetime import UTC, datetime

from app.storage.database import connect, initialize_schema, resolve_database_path
from app.storage.models import OpportunityRecord, OpportunityStatus
from app.storage.repository import OpportunityRepository


def _sample_record() -> OpportunityRecord:
    now = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)
    return OpportunityRecord(
        id=None,
        product_name="Chanel Wallet",
        brand="Chanel",
        category="wallet",
        purchase_source="Fashionphile",
        purchase_url="https://example.invalid/chanel-wallet",
        purchase_price=120000.0,
        selling_market="Yahoo Auction",
        selling_url="https://example.invalid/yahoo/chanel-wallet",
        selling_price=180000.0,
        estimated_profit=35000.0,
        profit_margin=29.2,
        demand_score=88.0,
        turnover_score=76.5,
        arbitrage_score=82.4,
        decision="BUY",
        status=OpportunityStatus.NEW,
        created_at=now,
        updated_at=now,
    )


def test_sqlite_create_and_initialize_schema(tmp_path) -> None:
    db_path = tmp_path / "brand_profit.db"
    connection = connect(db_path)
    try:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='opportunities'"
        ).fetchone()
        assert tables is not None
    finally:
        connection.close()
    assert resolve_database_path(db_path) == db_path


def test_opportunity_repository_save_and_read(tmp_path) -> None:
    repository = OpportunityRepository(tmp_path / "brand_profit.db")
    saved = repository.save(_sample_record())

    assert saved.id is not None
    loaded = repository.get_by_id(saved.id)
    assert loaded is not None
    assert loaded.product_name == "Chanel Wallet"
    assert loaded.estimated_profit == 35000.0
    assert loaded.status is OpportunityStatus.NEW


def test_opportunity_repository_update_status(tmp_path) -> None:
    repository = OpportunityRepository(tmp_path / "brand_profit.db")
    saved = repository.save(_sample_record())

    updated = repository.update_status(saved.id, OpportunityStatus.WATCHING)

    assert updated is not None
    assert updated.status is OpportunityStatus.WATCHING
    reloaded = repository.get_by_id(saved.id)
    assert reloaded is not None
    assert reloaded.status is OpportunityStatus.WATCHING


def test_initialize_schema_is_idempotent(tmp_path) -> None:
    db_path = tmp_path / "brand_profit.db"
    connection = connect(db_path)
    initialize_schema(connection)
    initialize_schema(connection)
    connection.close()

    repository = OpportunityRepository(db_path)
    assert repository.list_all() == []
