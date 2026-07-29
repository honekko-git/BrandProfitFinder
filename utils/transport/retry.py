"""Retry and exponential backoff policy for marketplace transport."""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from config.transport import TransportSettings
from utils.transport.exceptions import (
    MarketplaceAuthenticationError,
    MarketplaceConnectionError,
    MarketplaceRateLimitError,
    MarketplaceTimeoutError,
    MarketplaceTransportError,
)

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
NON_RETRYABLE_STATUS_CODES = frozenset({400, 401, 403, 404})


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Outcome of retry policy evaluation."""

    should_retry: bool
    exception: MarketplaceTransportError | None = None


def compute_backoff_seconds(attempt_index: int, settings: TransportSettings) -> float:
    """
    Compute exponential backoff delay.

    Example with base=1: attempt 0 -> 1s, attempt 1 -> 2s, attempt 2 -> 4s.
    """
    delay = settings.backoff_base_seconds * (2**attempt_index)
    return min(delay, settings.backoff_max_seconds)


def is_retryable_status(status_code: int) -> bool:
    """Return True when an HTTP status should trigger retry."""
    return status_code in RETRYABLE_STATUS_CODES


def evaluate_http_status(
    status_code: int,
    *,
    marketplace_name: str,
    retry_count: int,
) -> RetryDecision:
    """Map HTTP status to retry or terminal transport exception."""
    if status_code in NON_RETRYABLE_STATUS_CODES:
        if status_code in {401, 403}:
            return RetryDecision(
                should_retry=False,
                exception=MarketplaceAuthenticationError(
                    f"authentication failed with HTTP {status_code}",
                    marketplace_name=marketplace_name,
                    status_code=status_code,
                    retry_count=retry_count,
                ),
            )
        return RetryDecision(
            should_retry=False,
            exception=MarketplaceTransportError(
                f"non-retryable HTTP {status_code}",
                marketplace_name=marketplace_name,
                status_code=status_code,
                retry_count=retry_count,
            ),
        )

    if is_retryable_status(status_code):
        if status_code == 429:
            return RetryDecision(
                should_retry=True,
                exception=MarketplaceRateLimitError(
                    "rate limit exceeded",
                    marketplace_name=marketplace_name,
                    status_code=status_code,
                    retry_count=retry_count,
                ),
            )
        return RetryDecision(should_retry=True)

    if 200 <= status_code < 300:
        return RetryDecision(should_retry=False)

    if status_code >= 500:
        return RetryDecision(should_retry=True)

    return RetryDecision(
        should_retry=False,
        exception=MarketplaceTransportError(
            f"unexpected HTTP {status_code}",
            marketplace_name=marketplace_name,
            status_code=status_code,
            retry_count=retry_count,
        ),
    )


def map_request_exception(
    exc: Exception,
    *,
    marketplace_name: str,
    retry_count: int,
) -> RetryDecision:
    """Map httpx request exceptions to retry decisions."""
    if isinstance(exc, httpx.TimeoutException):
        return RetryDecision(
            should_retry=True,
            exception=MarketplaceTimeoutError(
                str(exc) or "request timed out",
                marketplace_name=marketplace_name,
                retry_count=retry_count,
            ),
        )
    if isinstance(exc, httpx.ConnectError):
        return RetryDecision(
            should_retry=True,
            exception=MarketplaceConnectionError(
                str(exc) or "connection failed",
                marketplace_name=marketplace_name,
                retry_count=retry_count,
            ),
        )
    if isinstance(exc, httpx.RequestError):
        return RetryDecision(
            should_retry=True,
            exception=MarketplaceConnectionError(
                str(exc) or "request failed",
                marketplace_name=marketplace_name,
                retry_count=retry_count,
            ),
        )
    return RetryDecision(
        should_retry=False,
        exception=MarketplaceTransportError(
            str(exc),
            marketplace_name=marketplace_name,
            retry_count=retry_count,
        ),
    )


def sleep_backoff(attempt_index: int, settings: TransportSettings) -> None:
    """Sleep for the configured exponential backoff interval."""
    delay = compute_backoff_seconds(attempt_index, settings)
    if delay > 0:
        time.sleep(delay)
