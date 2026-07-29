"""Version 2 shared HTTP transport configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TransportSettings:
    """Global defaults for marketplace HTTP transport."""

    timeout_seconds: float = 30.0
    max_retries: int = 3
    backoff_base_seconds: float = 1.0
    backoff_max_seconds: float = 4.0

    @classmethod
    def from_env(cls) -> TransportSettings:
        """Load transport settings from environment variables."""
        return cls(
            timeout_seconds=max(0.1, float(os.getenv("TRANSPORT_TIMEOUT_SECONDS", "30"))),
            max_retries=max(0, int(os.getenv("TRANSPORT_MAX_RETRIES", os.getenv("MAX_RETRY", "3")))),
            backoff_base_seconds=max(0.0, float(os.getenv("TRANSPORT_BACKOFF_BASE_SECONDS", "1"))),
            backoff_max_seconds=max(0.0, float(os.getenv("TRANSPORT_BACKOFF_MAX_SECONDS", "4"))),
        )


DEFAULT_TRANSPORT_SETTINGS = TransportSettings.from_env()
