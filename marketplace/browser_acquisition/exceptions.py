"""Exceptions for controlled browser acquisition."""

from __future__ import annotations

from enum import StrEnum


class BlockingReason(StrEnum):
    """Explicit blocking reason for failed acquisition."""

    BLOCKED_BY_SITE = "BLOCKED_BY_SITE"
    CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
    SELECTOR_NOT_FOUND = "SELECTOR_NOT_FOUND"
    NO_RESULTS = "NO_RESULTS"
    SOLD_PRICE_NOT_AVAILABLE = "SOLD_PRICE_NOT_AVAILABLE"
    NETWORK_ERROR = "NETWORK_ERROR"
    POLICY_RESTRICTION = "POLICY_RESTRICTION"
    PLAYWRIGHT_UNAVAILABLE = "PLAYWRIGHT_UNAVAILABLE"


class AcquisitionBlockedError(Exception):
    """Raised when browser acquisition is blocked or unavailable."""

    def __init__(self, reason: BlockingReason, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = reason.value if not detail else f"{reason.value}: {detail}"
        super().__init__(message)
