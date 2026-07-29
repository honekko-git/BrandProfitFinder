"""Contract tests for marketplace-independent market signal models."""

from __future__ import annotations

import importlib
import pkgutil

from market_intelligence.extractor import extract_market_signals
from market_intelligence.models import MarketSignals
from models.marketplace_listing import MarketplaceListing


def test_market_signals_default_values_are_none() -> None:
    signals = MarketSignals()

    assert signals.competition_score is None
    assert signals.price_stability_score is None
    assert signals.demand_score is None
    assert signals.inventory_risk_score is None
    assert signals.confidence_score is None


def test_market_signals_to_metadata_uses_contract_keys() -> None:
    signals = MarketSignals(
        competition_score=0.1,
        price_stability_score=0.2,
        demand_score=0.3,
        inventory_risk_score=0.4,
        confidence_score=0.5,
    )

    metadata = signals.to_metadata()

    assert metadata == {
        "competition_score": 0.1,
        "price_stability_score": 0.2,
        "demand_score": 0.3,
        "inventory_risk_score": 0.4,
        "market_signal_confidence_score": 0.5,
    }


def test_extractor_returns_placeholder_defaults_without_metadata() -> None:
    listing = MarketplaceListing(
        marketplace_name="demo",
        listing_id="D-1",
        title="Sample",
        price_jpy=10000,
    )

    signals = extract_market_signals(listing)

    assert signals == MarketSignals()


def test_extractor_passes_through_standard_metadata_keys() -> None:
    listing = MarketplaceListing(
        marketplace_name="demo",
        listing_id="D-2",
        title="Sample",
        price_jpy=10000,
        source_metadata={
            "competition_score": 0.55,
            "demand_score": 0.66,
            "market_signal_confidence_score": 0.77,
        },
    )

    signals = extract_market_signals(listing)

    assert signals.competition_score == 0.55
    assert signals.demand_score == 0.66
    assert signals.confidence_score == 0.77
    assert signals.price_stability_score is None
    assert signals.inventory_risk_score is None


def test_extractor_has_no_marketplace_client_dependencies() -> None:
    package = importlib.import_module("market_intelligence")
    module_names = [
        module_info.name
        for module_info in pkgutil.walk_packages(package.__path__, package.__name__ + ".")
    ]

    for module_name in module_names:
        module = importlib.import_module(module_name)
        source = module.__file__ or ""
        assert "marketplace/" not in source.replace("\\", "/")
        assert "utils/transport" not in source.replace("\\", "/")
