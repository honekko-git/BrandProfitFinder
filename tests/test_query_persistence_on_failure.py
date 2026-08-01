"""Query persistence on acquisition failure (empty-query root-cause fix)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from marketplace.browser_acquisition.exceptions import AcquisitionBlockedError, BlockingReason
from profit_discovery.discovery_validation.batch_profit.costs import default_cost_profiles
from profit_discovery.discovery_validation.batch_profit.models import BatchProfitCandidate
from profit_discovery.discovery_validation.batch_profit.pipeline import (
    CachedYahooSearchService,
    _process_candidate,
)


def _candidate(**kwargs) -> BatchProfitCandidate:
    defaults = dict(
        candidate_id="ac-test-ref",
        title="Prada Acetate Oval Sunglasses SPR 26Z Black",
        brand="Prada",
        category="Sunglasses",
        purchase_price=Decimal("450"),
        currency="USD",
        purchase_price_jpy=Decimal("67500"),
        purchase_url="https://example.com/x",
        purchase_source="Fashionphile",
        condition="Good",
        detected_subtype="Sunglasses",
        detected_material="Acetate",
    )
    defaults.update(kwargs)
    return BatchProfitCandidate(**defaults)


def test_yahoo_exception_preserves_generated_queries() -> None:
    search = MagicMock()
    search.fetch_for_candidate.side_effect = RuntimeError("BrowserType.launch: missing")
    open_acq = MagicMock()
    open_acq.acquire_multi.return_value = ([], [])
    mercari = MagicMock()
    mercari.acquire_multi.side_effect = AcquisitionBlockedError(
        BlockingReason.PLAYWRIGHT_UNAVAILABLE, "missing binary"
    )

    result = _process_candidate(
        candidate=_candidate(),
        search_service=search,
        open_acquirer=open_acq,
        mercari_acquirer=mercari,
        calculator=MagicMock(),
        discovery_engine=MagicMock(),
        buy_engine=MagicMock(),
        validator=MagicMock(),
        cost_profile=default_cost_profiles()["standard"],
        html_by_query=None,
        open_html_by_query=None,
        mercari_html_by_query=None,
    )
    assert result.yahoo_queries
    assert any("SPR26Z" in q for q in result.yahoo_queries)
    trace = result.operational_trace
    assert trace["yahoo"]["queries"]
    assert trace["query_generation"]["status"] in {"OK", "OK_WITH_CATEGORY_FALLBACK"}
    assert trace["query_generation"]["queries"]


def test_cached_yahoo_fetch_accepts_prebuilt_queries() -> None:
    cache = MagicMock()
    cache.get.return_value = None
    acquirer = MagicMock()
    acquirer.acquire.side_effect = AcquisitionBlockedError(BlockingReason.PLAYWRIGHT_UNAVAILABLE, "x")
    acquirer.last_diagnostics = []
    service = CachedYahooSearchService(cache_repository=cache, yahoo_acquirer=acquirer, use_cache=False)
    samples, queries, source, *_ = service.fetch_for_candidate(
        title="t",
        brand="Prada",
        category="Bag",
        queries=("プラダ SPR26Z", "Prada SPR26Z"),
    )
    assert samples == []
    assert queries == ("プラダ SPR26Z", "Prada SPR26Z")
