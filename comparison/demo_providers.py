"""
Demo marketplace providers for cross-marketplace comparison.
"""

from __future__ import annotations

import json
from pathlib import Path

from marketplace.base_marketplace import BaseMarketplace
from marketplace.goat_client import FakeGoatClient
from marketplace.goat_marketplace import create_goat_marketplace
from marketplace.goat_settings import GoatSettings
from marketplace.stockx_client import FakeStockXClient
from marketplace.stockx_marketplace import create_stockx_marketplace
from marketplace.stockx_settings import StockXSettings

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def build_comparison_demo_marketplaces() -> list[BaseMarketplace]:
    """
    Build deterministic demo marketplaces for cross-marketplace comparison.

    Uses synthetic internal fixtures only. No network access.
    """
    marketplaces: list[BaseMarketplace] = []
    stockx_payload = _load_fixture("comparison_phase3_stockx.json")
    goat_payload = _load_fixture("comparison_phase3_goat.json")
    if stockx_payload is not None:
        marketplaces.append(
            create_stockx_marketplace(
                client=FakeStockXClient(stockx_payload, filter_by_query=True),
                settings=StockXSettings.from_env(),
            )
        )
    if goat_payload is not None:
        marketplaces.append(
            create_goat_marketplace(
                client=FakeGoatClient(goat_payload, filter_by_query=True),
                settings=GoatSettings.from_env(),
            )
        )
    return marketplaces


def comparison_demo_expected_marketplaces() -> list[str]:
    """Return expected marketplace names for the comparison demo."""
    return ["stockx", "goat"]


def _load_fixture(name: str) -> dict[str, object] | None:
    path = FIXTURES_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
