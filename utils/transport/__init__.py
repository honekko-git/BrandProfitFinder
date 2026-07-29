"""Version 2 shared HTTP transport foundation for marketplace adapters."""

from utils.transport.exceptions import (
    MarketplaceAuthenticationError,
    MarketplaceConnectionError,
    MarketplaceRateLimitError,
    MarketplaceTimeoutError,
    MarketplaceTransportError,
)
from utils.transport.models import TransportRequest, TransportRequestMetadata, TransportResponse
from utils.transport.transport import HttpTransport, build_default_headers

__all__ = [
    "HttpTransport",
    "MarketplaceAuthenticationError",
    "MarketplaceConnectionError",
    "MarketplaceRateLimitError",
    "MarketplaceTimeoutError",
    "MarketplaceTransportError",
    "TransportRequest",
    "TransportRequestMetadata",
    "TransportResponse",
    "build_default_headers",
]
