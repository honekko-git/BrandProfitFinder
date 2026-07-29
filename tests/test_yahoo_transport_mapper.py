"""Unit tests for Yahoo transport exception mapping."""

import pytest

from marketplace.yahoo_exceptions import (
    YahooApiError,
    YahooClientError,
    YahooRateLimitError,
    YahooServerError,
)
from marketplace.yahoo_transport_mapper import map_transport_exception
from utils.transport.exceptions import (
    MarketplaceAuthenticationError,
    MarketplaceConnectionError,
    MarketplaceRateLimitError,
    MarketplaceTimeoutError,
    MarketplaceTransportError,
)


@pytest.mark.parametrize(
    "exc,expected_type",
    [
        (MarketplaceRateLimitError("rate limit", status_code=429), YahooRateLimitError),
        (MarketplaceAuthenticationError("auth", status_code=401), YahooClientError),
        (MarketplaceAuthenticationError("auth", status_code=403), YahooClientError),
        (MarketplaceTimeoutError("timeout"), YahooApiError),
        (MarketplaceConnectionError("connection"), YahooApiError),
        (MarketplaceTransportError("missing", status_code=404), YahooClientError),
        (MarketplaceTransportError("bad request", status_code=400), YahooClientError),
        (MarketplaceTransportError("unavailable", status_code=503), YahooServerError),
        (MarketplaceTransportError("server", status_code=500), YahooServerError),
    ],
)
def test_map_transport_exception(exc, expected_type) -> None:
    mapped = map_transport_exception(exc)
    assert isinstance(mapped, expected_type)


def test_map_transport_exception_timeout_message() -> None:
    mapped = map_transport_exception(MarketplaceTimeoutError("timeout"))
    assert str(mapped) == "Yahoo API request timed out"


def test_map_transport_exception_connection_message() -> None:
    mapped = map_transport_exception(MarketplaceConnectionError("connection"))
    assert str(mapped) == "Yahoo API connection error"


def test_map_transport_exception_404_message() -> None:
    mapped = map_transport_exception(MarketplaceTransportError("missing", status_code=404))
    assert str(mapped) == "Yahoo API client error: HTTP 404"
