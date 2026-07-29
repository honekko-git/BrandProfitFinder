"""Supplier runtime configuration for fixture and live client selection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SupplierRuntimeConfig:
    """Controls whether supplier resolution prefers fixture or live clients."""

    use_fixture: bool = True
    enable_live: bool = False

    @classmethod
    def default(cls) -> SupplierRuntimeConfig:
        """Return the default runtime configuration."""
        return cls()

    @classmethod
    def fixture_only(cls) -> SupplierRuntimeConfig:
        """Return configuration that resolves fixture clients only."""
        return cls(use_fixture=True, enable_live=False)

    @classmethod
    def live_only(cls) -> SupplierRuntimeConfig:
        """Return configuration that attempts live clients only."""
        return cls(use_fixture=False, enable_live=True)
