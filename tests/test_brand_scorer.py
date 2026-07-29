"""Tests for brand scoring foundation."""

from __future__ import annotations

from profit_intelligence.scorers.brand_scorer import BrandScorer, BrandTierConfig


def test_known_tier_s_brand_scores_100() -> None:
    score = BrandScorer().score(metadata={"brand": "gucci"})

    assert score.score == 100.0
    assert "Strong brand confidence." in score.reasons


def test_known_tier_a_brand_scores_80() -> None:
    score = BrandScorer().score(metadata={"brand": "dior"})

    assert score.score == 80.0


def test_unknown_brand_scores_neutral_50() -> None:
    score = BrandScorer().score(metadata={"brand": "unknown-label"})

    assert score.score == 50.0
    assert score.reasons


def test_custom_brand_tiers_are_configurable() -> None:
    config = BrandTierConfig(
        tier_s=frozenset({"alpha"}),
        tier_a=frozenset({"beta"}),
        tier_b=frozenset({"gamma"}),
    )
    scorer = BrandScorer(config)

    assert scorer.score(metadata={"brand": "alpha"}).score == 100.0
    assert scorer.score(metadata={"brand": "beta"}).score == 80.0
    assert scorer.score(metadata={"brand": "gamma"}).score == 60.0
