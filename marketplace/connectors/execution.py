"""Execution metadata for market connector resolution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MarketConnectorExecutionResult:
    """Truth tracking for requested vs actual market connector source."""

    requested_source: str
    actual_source: str
    fallback_used: bool
    market_name: str
