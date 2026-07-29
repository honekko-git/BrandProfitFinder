"""Unit tests for Rakuten transport exception mapping."""

import pytest

from marketplace.rakuten_exceptions import (
    RakutenApiError,
    RakutenClientError,
    RakutenNotFoundError,
    RakutenRateLimitError,
    RakutenServerError,
    RakutenServiceUnavailableError,
)
from marketplace.rakuten_transport_mapper import map_transport_exception
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
        (MarketplaceRateLimitError("rate limit", status_code=429), RakutenRateLimitError),
        (MarketplaceAuthenticationError("auth", status_code=401), RakutenApiError),
        (MarketplaceAuthenticationError("auth", status_code=403), RakutenApiError),
        (MarketplaceTimeoutError("timeout"), RakutenApiError),
        (MarketplaceConnectionError("connection"), RakutenApiError),
        (MarketplaceTransportError("missing", status_code=404), RakutenNotFoundError),
        (MarketplaceTransportError("bad request", status_code=400), RakutenClientError),
        (MarketplaceTransportError("unavailable", status_code=503), RakutenServiceUnavailableError),
        (MarketplaceTransportError("server", status_code=500), RakutenServerError),
    ],
)
def test_map_transport_exception(exc, expected_type) -> None:
    mapped = map_transport_exception(exc)
    assert isinstance(mapped, expected_type)
