"""Sales demand analysis for discovery queries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from profit_intelligence.demand.models import SalesDemandProfile

DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "demand"


class DemandAnalyzer:
    """Build sales demand profiles from sold-market observations."""

    def __init__(self, *, fixture_dir: Path | str | None = None) -> None:
        self._fixture_dir = Path(fixture_dir) if fixture_dir is not None else DEFAULT_FIXTURE_DIR

    def analyze(self, query: str, sold_data: dict[str, Any]) -> SalesDemandProfile:
        """Analyze one query using supplied sold-market data."""
        profile = SalesDemandProfile(
            query=query,
            period_days=int(sold_data["period_days"]),
            sold_count=int(sold_data["sold_count"]),
            average_sold_price_jpy=float(sold_data["average_sold_price_jpy"]),
            sell_through_rate=float(sold_data["sell_through_rate"]),
            demand_score=0.0,
        )
        return SalesDemandProfile(
            query=profile.query,
            period_days=profile.period_days,
            sold_count=profile.sold_count,
            average_sold_price_jpy=profile.average_sold_price_jpy,
            sell_through_rate=profile.sell_through_rate,
            demand_score=profile.calculate_demand_score(),
        )

    def analyze_fixture(self, fixture_name: str) -> SalesDemandProfile:
        """Analyze one demand fixture file by name."""
        payload = self._load_fixture(fixture_name)
        query = str(payload["query"])
        sold_data = {
            key: payload[key]
            for key in (
                "period_days",
                "sold_count",
                "average_sold_price_jpy",
                "sell_through_rate",
            )
        }
        return self.analyze(query, sold_data)

    def batch_analyze(self, products: list[dict[str, Any]]) -> list[SalesDemandProfile]:
        """Analyze multiple product demand payloads."""
        profiles: list[SalesDemandProfile] = []
        for product in products:
            query = str(product["query"])
            sold_data = dict(product.get("sold_data", product))
            profiles.append(self.analyze(query, sold_data))
        return profiles

    def _load_fixture(self, fixture_name: str) -> dict[str, Any]:
        path = self._fixture_dir / fixture_name
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid demand fixture payload: {fixture_name}")
        return payload
