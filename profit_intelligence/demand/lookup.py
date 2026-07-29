"""Fixture-backed demand profile lookup."""

from __future__ import annotations

from pathlib import Path

from profit_intelligence.demand.analyzer import DEFAULT_FIXTURE_DIR, DemandAnalyzer
from profit_intelligence.demand.models import SalesDemandProfile


class DemandLookup:
    """Resolve sales demand profiles from normalized query strings."""

    def __init__(
        self,
        *,
        fixture_dir: Path | str | None = None,
        analyzer: DemandAnalyzer | None = None,
    ) -> None:
        active_fixture_dir = Path(fixture_dir) if fixture_dir is not None else DEFAULT_FIXTURE_DIR
        self._analyzer = analyzer or DemandAnalyzer(fixture_dir=active_fixture_dir)
        self._profiles_by_query = _load_fixture_index(self._analyzer, active_fixture_dir)

    def find(self, query: str) -> SalesDemandProfile | None:
        """Find one demand profile for a normalized query."""
        if not query.strip():
            return None
        return self._profiles_by_query.get(_normalize_lookup_key(query))

    def batch_find(self, queries: list[str]) -> list[SalesDemandProfile | None]:
        """Find demand profiles for multiple normalized queries."""
        return [self.find(query) for query in queries]


def _load_fixture_index(
    analyzer: DemandAnalyzer,
    fixture_dir: Path,
) -> dict[str, SalesDemandProfile]:
    profiles: dict[str, SalesDemandProfile] = {}
    for fixture_path in sorted(fixture_dir.glob("*.json")):
        profile = analyzer.analyze_fixture(fixture_path.name)
        profiles[_normalize_lookup_key(profile.query)] = profile
    return profiles


def _normalize_lookup_key(query: str) -> str:
    return " ".join(query.strip().lower().split())
