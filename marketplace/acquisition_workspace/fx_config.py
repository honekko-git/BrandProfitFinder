"""Configurable FX freshness thresholds and provider settings."""

from __future__ import annotations

import os


def fresh_max_age_seconds() -> int:
    """Rates retrieved within this age are FRESH."""
    return max(60, int(os.getenv("FX_FRESH_MAX_AGE_SECONDS", str(24 * 3600))))


def stale_max_age_seconds() -> int:
    """Stored rates older than fresh but within this age may be used as STALE fallback."""
    fresh = fresh_max_age_seconds()
    stale = max(fresh, int(os.getenv("FX_STALE_MAX_AGE_SECONDS", str(7 * 24 * 3600))))
    return stale


def provider_timeout_seconds() -> float:
    return max(1.0, float(os.getenv("FX_PROVIDER_TIMEOUT_SECONDS", "10")))


def provider_max_retries() -> int:
    return max(0, int(os.getenv("FX_PROVIDER_MAX_RETRIES", "2")))


def frankfurter_base_url() -> str:
    """Server-configured provider only — never accept browser-supplied URLs."""
    return os.getenv(
        "FX_PROVIDER_URL",
        "https://api.frankfurter.app/latest",
    ).strip()


def live_fx_disabled() -> bool:
    """Test/ops switch to force fallback path without live HTTP."""
    return os.getenv("FX_LIVE_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}
