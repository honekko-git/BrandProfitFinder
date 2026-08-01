"""Configuration helpers for real profit verification."""

from __future__ import annotations

import os

from config.settings import DEFAULT_EXCHANGE_RATE

from profit_discovery.discovery_validation.real_profit_models import EndpointStatus


def resolve_usd_jpy_exchange_rate() -> float:
    """Resolve USD/JPY rate from USD_JPY_EXCHANGE_RATE or project default."""
    raw = os.getenv("USD_JPY_EXCHANGE_RATE", "").strip()
    if raw:
        return float(raw)
    return float(DEFAULT_EXCHANGE_RATE)


def resolve_currency_jpy_exchange_rate(currency: str) -> float:
    """Resolve currency→JPY using existing env/default path. Never treats EUR/GBP as USD.

    Supported:
    - JPY → 1.0
    - USD → resolve_usd_jpy_exchange_rate()
    - EUR → EUR_JPY_EXCHANGE_RATE or DEFAULT_EUR_JPY_EXCHANGE_RATE (default 170)
    - GBP → GBP_JPY_EXCHANGE_RATE or DEFAULT_GBP_JPY_EXCHANGE_RATE (default 200)

    Raises ValueError for unsupported/blank currencies.
    """
    code = str(currency or "").strip().upper()
    if not code:
        raise ValueError("currency is required")
    if code == "JPY":
        return 1.0
    if code == "USD":
        return resolve_usd_jpy_exchange_rate()
    if code == "EUR":
        raw = os.getenv("EUR_JPY_EXCHANGE_RATE", "").strip()
        if raw:
            return float(raw)
        return float(os.getenv("DEFAULT_EUR_JPY_EXCHANGE_RATE", "170.0"))
    if code == "GBP":
        raw = os.getenv("GBP_JPY_EXCHANGE_RATE", "").strip()
        if raw:
            return float(raw)
        return float(os.getenv("DEFAULT_GBP_JPY_EXCHANGE_RATE", "200.0"))
    raise ValueError(f"unsupported currency: {code}")


def fashionphile_endpoint_status() -> EndpointStatus:
    """Report whether Fashionphile live endpoint is configured."""
    url = os.getenv("FASHIONPHILE_API_URL", "").strip()
    if url:
        return EndpointStatus(name="Fashionphile", configured=True, detail=url)
    return EndpointStatus(
        name="Fashionphile",
        configured=False,
        detail="FASHIONPHILE_API_URL is not configured",
    )


def yahoo_auction_endpoint_status() -> EndpointStatus:
    """Report whether Yahoo Auction sold-data endpoint is configured."""
    endpoint = os.getenv("YAHOO_AUCTION_DATA_SOURCE", "").strip()
    api_key = os.getenv("YAHOO_CLIENT_ID", "").strip()
    if endpoint and api_key:
        return EndpointStatus(name="Yahoo Auction", configured=True, detail=endpoint)
    missing = []
    if not endpoint:
        missing.append("YAHOO_AUCTION_DATA_SOURCE")
    if not api_key:
        missing.append("YAHOO_CLIENT_ID")
    return EndpointStatus(
        name="Yahoo Auction",
        configured=False,
        detail=" / ".join(missing) + " not configured",
    )
