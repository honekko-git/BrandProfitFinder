"""Playwright browser session for controlled page acquisition."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from marketplace.browser_acquisition.exceptions import AcquisitionBlockedError, BlockingReason
from marketplace.browser_acquisition.rate_limit import RateLimiter

CAPTCHA_PATTERNS = (
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"captcha",
        r"verify you are human",
        r"are you a robot",
        r"access denied",
        r"unusual traffic",
        r"bot detection",
    )
)

BLOCKED_STATUS_CODES = {401, 403, 429, 503}


@dataclass(frozen=True, slots=True)
class BrowserFetchResult:
    """One browser page fetch result."""

    url: str
    html: str
    status_code: int
    blocked_reason: str = ""


class BrowserSession:
    """Low-frequency Playwright session for public page reads."""

    def __init__(
        self,
        *,
        headless: bool = True,
        timeout_ms: int = 30_000,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._rate_limiter = rate_limiter or RateLimiter(min_interval_seconds=2.0)

    def fetch_html(self, url: str, *, wait_selector: str | None = None) -> BrowserFetchResult:
        """Fetch one public page and return HTML without storing cookies."""
        try:
            import asyncio

            asyncio.get_running_loop()
            in_async = True
        except RuntimeError:
            in_async = False
        if in_async:
            with ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(self._fetch_html_sync, url, wait_selector).result()
        return self._fetch_html_sync(url, wait_selector)

    def _fetch_html_sync(self, url: str, wait_selector: str | None = None) -> BrowserFetchResult:
        """Fetch one page using the sync Playwright API."""
        self._rate_limiter.wait()
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise AcquisitionBlockedError(
                BlockingReason.PLAYWRIGHT_UNAVAILABLE,
                "Install playwright and run: playwright install chromium",
            ) from exc

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self._headless)
                try:
                    context = browser.new_context(
                        user_agent=(
                            "BrandProfitFinder/1.0 (+controlled-live-check; "
                            "low-frequency public page read)"
                        ),
                        java_script_enabled=True,
                    )
                    page = context.new_page()
                    response = page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
                    if wait_selector:
                        try:
                            page.wait_for_selector(wait_selector, timeout=min(15_000, self._timeout_ms))
                        except Exception:
                            pass
                    html = page.content()
                    status_code = response.status if response is not None else 0
                finally:
                    browser.close()
        except AcquisitionBlockedError:
            raise
        except Exception as exc:
            # Missing browser binary / launch failures must not wipe query traces upstream.
            raise AcquisitionBlockedError(
                BlockingReason.PLAYWRIGHT_UNAVAILABLE,
                f"{type(exc).__name__}: {exc}",
            ) from exc

        blocked_reason = detect_blocking(html, status_code)
        return BrowserFetchResult(
            url=url,
            html=html,
            status_code=status_code,
            blocked_reason=blocked_reason,
        )


def detect_blocking(html: str, status_code: int) -> str:
    """Detect CAPTCHA or access blocks from page content or HTTP status."""
    if status_code in BLOCKED_STATUS_CODES:
        if status_code == 429:
            return BlockingReason.BLOCKED_BY_SITE.value
        if status_code == 403:
            return BlockingReason.POLICY_RESTRICTION.value
        return BlockingReason.BLOCKED_BY_SITE.value

    lowered = html.lower()
    for pattern in CAPTCHA_PATTERNS:
        if pattern.search(lowered):
            if "captcha" in lowered or "verify you are human" in lowered:
                return BlockingReason.CAPTCHA_REQUIRED.value
            return BlockingReason.BLOCKED_BY_SITE.value
    return ""
