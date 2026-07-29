"""Fashionphile supplier live integration settings."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class FashionphileSettings:
    """Configuration for Fashionphile supplier live integration."""

    enabled: bool = False
    use_live: bool = False
    endpoint: str | None = None
    api_key: str | None = None

    @classmethod
    def default(cls) -> FashionphileSettings:
        """Return default disabled supplier settings."""
        return cls()

    @classmethod
    def from_env(cls) -> FashionphileSettings:
        """Load Fashionphile supplier settings from environment variables."""
        return cls(
            enabled=_env_bool("FASHIONPHILE_SUPPLIER_ENABLED", False),
            use_live=_env_bool("FASHIONPHILE_SUPPLIER_USE_LIVE", False),
            endpoint=os.getenv("FASHIONPHILE_SUPPLIER_ENDPOINT"),
            api_key=os.getenv("FASHIONPHILE_SUPPLIER_API_KEY"),
        )

    @property
    def live_enabled(self) -> bool:
        """Return True when live search should be attempted."""
        return self.enabled and self.use_live
