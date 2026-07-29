"""Tests for fixture-backed demand lookup."""

from __future__ import annotations

from pathlib import Path

from profit_intelligence.demand import DemandLookup


def test_demand_lookup_finds_fixture_profile() -> None:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / "demand"
    lookup = DemandLookup(fixture_dir=fixture_dir)

    profile = lookup.find("Chanel Wallet")

    assert profile is not None
    assert profile.query == "Chanel Wallet"
    assert profile.sold_count == 35


def test_demand_lookup_returns_none_for_unknown_query() -> None:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / "demand"
    lookup = DemandLookup(fixture_dir=fixture_dir)

    assert lookup.find("Unknown Brand Wallet") is None


def test_demand_lookup_batch_find_preserves_order() -> None:
    fixture_dir = Path(__file__).resolve().parent / "fixtures" / "demand"
    lookup = DemandLookup(fixture_dir=fixture_dir)

    profiles = lookup.batch_find(["Chanel Wallet", "Unknown Query", "Dior Bag"])

    assert profiles[0] is not None
    assert profiles[0].query == "Chanel Wallet"
    assert profiles[1] is None
    assert profiles[2] is not None
    assert profiles[2].query == "Dior Bag"
