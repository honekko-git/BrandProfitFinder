"""
Unified marketplace client resolution for live, demo, and injected clients.
"""

from __future__ import annotations

from typing import Any

from marketplace.amazon_api_client import AmazonApiClient
from marketplace.amazon_client import AmazonClientProtocol, FakeAmazonClient
from marketplace.amazon_settings import AmazonConfig
from marketplace.rakuten_client import FakeRakutenClient, RakutenApiClient, RakutenClientProtocol
from marketplace.rakuten_settings import RakutenConfig
from marketplace.yahoo_api_client import YahooApiClient
from marketplace.yahoo_settings import YahooApiSettings


def resolve_rakuten_client(
    explicit: RakutenClientProtocol | None = None,
    config: RakutenConfig | None = None,
    *,
    demo_payload: dict[str, Any] | None = None,
) -> RakutenClientProtocol | None:
    """
    Resolve a Rakuten client using injection, demo, live, or none priority.

    Priority:
        1. Explicit injected client
        2. Demo client when demo mode is enabled
        3. Live API client when enabled and configured
        4. None
    """
    if explicit is not None:
        return explicit

    settings = config or RakutenConfig.from_env()

    if settings.can_demo:
        return FakeRakutenClient(demo_payload)

    if settings.can_execute:
        return RakutenApiClient.from_settings(settings)

    return None


def resolve_yahoo_client(
    explicit: YahooApiClient | None = None,
    settings: YahooApiSettings | None = None,
    *,
    demo_payload: dict[str, Any] | None = None,
) -> YahooApiClient | None:
    """
    Resolve a Yahoo Shopping client using injection, live, or none priority.

    Yahoo Shopping has no fake client; demo_payload is accepted for API symmetry only.

    Priority:
        1. Explicit injected client
        2. Live API client when enabled and configured
        3. None
    """
    del demo_payload  # Yahoo Shopping has no demo fake client in Version 1.

    if explicit is not None:
        return explicit

    config = settings or YahooApiSettings.from_env()

    if config.can_execute:
        return YahooApiClient.from_settings(config)

    return None


def resolve_amazon_client(
    explicit: AmazonClientProtocol | None = None,
    config: AmazonConfig | None = None,
    *,
    demo_payload: dict[str, Any] | None = None,
) -> AmazonClientProtocol | None:
    """
    Resolve an Amazon client using injection, demo, live, or none priority.

    Priority:
        1. Explicit injected client
        2. Demo client when demo mode is enabled
        3. Live API client when enabled and configured
        4. None
    """
    if explicit is not None:
        return explicit

    settings = config or AmazonConfig.from_env()

    if settings.enabled and settings.demo_enabled:
        return FakeAmazonClient(demo_payload)

    if settings.enabled and settings.is_configured:
        return AmazonApiClient.from_settings(settings)

    return None
