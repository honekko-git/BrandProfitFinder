"""Tests for marketplace-independent competition scoring."""

from __future__ import annotations

from decimal import Decimal

from market_intelligence.competition_scorer import score_competition
from market_intelligence.models import MarketSignals
from models.marketplace_listing import MarketplaceListing


def test_low_competition_scores_high_opportunity() -> None:
    listings = [
        MarketplaceListing(marketplace_name="demo", listing_id="1", title="A", price_jpy=Decimal("10000")),
    ]

    result = score_competition(listings=listings)

    assert result.score >= 85
    assert "Low competition." in result.reasons


def test_high_competition_scores_low_opportunity() -> None:
    listings = [
        MarketplaceListing(
            marketplace_name="demo",
            listing_id=str(index),
            title=f"Item {index}",
            price_jpy=Decimal(str(10000 + index * 1000)),
        )
        for index in range(10)
    ]

    result = score_competition(listings=listings)

    assert result.score <= 30
    assert "High competition." in result.reasons


def test_missing_competition_data_returns_neutral_score() -> None:
    result = score_competition()

    assert result.score == 50.0
    assert "Competition data unavailable." in result.warnings


def test_market_signal_competition_intensity_is_inverted_to_opportunity() -> None:
    signals = MarketSignals(competition_score=80.0)

    result = score_competition(signals=signals)

    assert result.score == 20.0
