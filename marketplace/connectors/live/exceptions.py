"""Exceptions for live market connectors."""


class MarketConnectorTransportError(RuntimeError):
    """Raised when live HTTP transport fails."""


class MarketConnectorParseError(RuntimeError):
    """Raised when live response parsing fails."""


class MarketConnectorConfigurationError(RuntimeError):
    """Raised when live connector configuration is invalid."""
