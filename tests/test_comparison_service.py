"""Tests for cross-marketplace comparison service."""

import copy
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from comparison.config import ComparisonConfig
from comparison.demo_providers import build_comparison_demo_marketplaces
from comparison.service import CrossMarketplaceComparisonService
from main import build_phase3_calculator, build_phase3_products
from profit_intelligence.service import ProfitIntelligenceService

FIXTURES = Path(__file__).parent / "fixtures"


def test_compare_products_stockx_and_goat() -> None:
    marketplaces = build_comparison_demo_marketplaces()
    assert len(marketplaces) == 2
    products = build_phase3_products()
    service = CrossMarketplaceComparisonService(
        config=ComparisonConfig(expected_marketplaces=("stockx", "goat"))
    )
    result = service.compare_products(
        products,
        marketplaces,
        build_phase3_calculator(),
    )
    assert len(result.products) == 3
    assert len(result.all_search_results) == 6
    assert len(result.ranked_price_results) == 3
    assert all(comparison.selected_review_marketplace for comparison in result.products)
    assert all(comparison.highest_profit_marketplace for comparison in result.products)


def test_products_not_mutated() -> None:
    marketplaces = build_comparison_demo_marketplaces()
    products = build_phase3_products()
    original = copy.deepcopy(products)
    CrossMarketplaceComparisonService().compare_products(
        products,
        marketplaces,
        build_phase3_calculator(),
    )
    assert products == original


def test_profit_intelligence_optional() -> None:
    marketplaces = build_comparison_demo_marketplaces()
    products = build_phase3_products()[:1]
    with patch.object(ProfitIntelligenceService, "score_results") as score_mock:
        CrossMarketplaceComparisonService().compare_products(
            products,
            marketplaces,
            build_phase3_calculator(),
            profit_intelligence=False,
        )
        score_mock.assert_not_called()

    run = CrossMarketplaceComparisonService().compare_products(
        products,
        marketplaces,
        build_phase3_calculator(),
        profit_intelligence=True,
    )
    assert run.ranked_price_results[0].profit_intelligence is not None


def test_no_network_access() -> None:
    marketplaces = build_comparison_demo_marketplaces()
    products = build_phase3_products()[:1]
    with patch("utils.http.fetch_url") as mock_fetch, patch("utils.http.HttpClient") as mock_client:
        CrossMarketplaceComparisonService().compare_products(
            products,
            marketplaces,
            build_phase3_calculator(),
        )
    mock_fetch.assert_not_called()
    mock_client.assert_not_called()
