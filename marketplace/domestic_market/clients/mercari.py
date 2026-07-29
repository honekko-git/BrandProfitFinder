"""Fixture-backed Mercari domestic market client."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_FIXTURE_DIR = (
    Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "domestic_market"
)


class FakeMercariDomesticMarketClient:
    """Search Mercari sold prices from fixtures without network access."""

    def __init__(
        self,
        prices: list[int] | None = None,
        *,
        should_fail: bool = False,
        fixture_dir: Path | str | None = None,
    ) -> None:
        self._inline_prices = prices
        self._should_fail = should_fail
        self._fixture_dir = Path(fixture_dir) if fixture_dir is not None else DEFAULT_FIXTURE_DIR

    @property
    def market_name(self) -> str:
        return "mercari"

    def search_sold_items(
        self,
        query: str,
        *,
        page: int = 1,
        max_results: int = 20,
    ) -> list[int]:
        if self._should_fail:
            raise RuntimeError("mercari search failed")

        if self._inline_prices is not None:
            start = max(page - 1, 0) * max_results
            end = start + max_results
            return self._inline_prices[start:end]

        normalized_query = query.strip().lower()
        matched_prices: list[int] = []
        for keyword, prices in self._load_fixture_entries():
            if not normalized_query or _matches_keyword(normalized_query, keyword):
                matched_prices.extend(prices)

        start = max(page - 1, 0) * max_results
        end = start + max_results
        return matched_prices[start:end]

    def _load_fixture_entries(self) -> list[tuple[str, list[int]]]:
        if not self._fixture_dir.exists():
            return []

        entries: list[tuple[str, list[int]]] = []
        for fixture_path in sorted(self._fixture_dir.glob("mercari_*.json")):
            payload = json.loads(fixture_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                continue
            parsed = _parse_fixture_payload(payload)
            if parsed is not None:
                entries.append(parsed)
        return entries


def _parse_fixture_payload(payload: dict[str, Any]) -> tuple[str, list[int]] | None:
    keyword = str(payload.get("product_keyword") or "")
    raw_prices = payload.get("sold_prices") or payload.get("prices") or []
    if not isinstance(raw_prices, list):
        return None
    prices = [int(price) for price in raw_prices if isinstance(price, (int, float))]
    return keyword.lower(), prices


def _matches_keyword(query: str, keyword: str) -> bool:
    haystack = keyword.lower()
    tokens = query.split()
    return all(token in haystack for token in tokens)
