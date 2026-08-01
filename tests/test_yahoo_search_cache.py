"""Tests for Yahoo search cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.storage.yahoo_cache_repository import YahooSearchCacheRepository
from marketplace.browser_acquisition.models import AcquisitionStatus, YahooSoldSample
from marketplace.browser_acquisition.yahoo_search_cache import (
    build_cache_entry,
    cache_age_hours,
    is_cache_valid,
    normalize_query,
)


def test_cache_hit_and_duplicate_query_prevention(tmp_path) -> None:
    db_path = tmp_path / "cache.db"
    repo = YahooSearchCacheRepository(database_path=db_path)
    samples = [
        YahooSoldSample(
            title="CHANEL wallet",
            sold_price_jpy=100000,
            retrieved_at=datetime.now(tz=UTC).isoformat(),
            source="Yahoo Auction",
        )
    ]
    entry = build_cache_entry(query="CHANEL wallet caviar black", samples=samples, diagnostics=[])
    repo.save(entry)
    cached = repo.get("CHANEL wallet caviar black")
    assert cached is not None
    assert cached.raw_sample_count == 1
    assert normalize_query(" CHANEL   wallet caviar black ") == cached.normalized_query


def test_cache_expiry(tmp_path) -> None:
    db_path = tmp_path / "cache.db"
    repo = YahooSearchCacheRepository(database_path=db_path)
    past = datetime.now(tz=UTC) - timedelta(hours=30)
    entry = build_cache_entry(query="expired query", samples=[], diagnostics=[], ttl_hours=1)
    expired_entry = build_cache_entry(query="expired query", samples=[], diagnostics=[])
    repo.save(entry)
    assert is_cache_valid((past).isoformat()) is False


def test_live_cache_source_label() -> None:
    entry = build_cache_entry(query="test", samples=[], diagnostics=[])
    assert entry.acquisition_status == AcquisitionStatus.LIVE.value
    assert cache_age_hours(entry.retrieved_at) >= 0
