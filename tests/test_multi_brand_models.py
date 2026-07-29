"""Tests for multi-brand discovery models."""

from __future__ import annotations

from profit_discovery.discovery_runner.models import BatchDiscoveryResult
from profit_discovery.multi_brand.models import (
    BrandDiscoveryResult,
    MultiBrandDiscoveryRequest,
    MultiBrandDiscoveryResult,
)


def test_multi_brand_discovery_request_creation() -> None:
    request = MultiBrandDiscoveryRequest(
        brands=["Chanel", "Gucci"],
        category="wallets",
        keyword="wallet",
        max_results_per_brand=5,
    )

    assert request.brands == ["Chanel", "Gucci"]
    assert request.category == "wallets"
    assert request.keyword == "wallet"
    assert request.max_results_per_brand == 5


def test_multi_brand_discovery_result_creation() -> None:
    batch = BatchDiscoveryResult(
        total_products=1,
        evaluated_products=1,
        buy_candidates=0,
        results=(),
    )
    brand_result = BrandDiscoveryResult(brand="Chanel", batch_result=batch)
    result = MultiBrandDiscoveryResult(
        results=(brand_result,),
        ranked_candidates=(),
        ranked_opportunities=(),
        successful_brands=("Chanel",),
        failed_brands=(),
        total_candidates=0,
        metadata={"keyword": "wallet"},
    )

    assert len(result.results) == 1
    assert result.successful_brands == ("Chanel",)
    assert result.failed_brands == ()
    assert result.total_candidates == 0
