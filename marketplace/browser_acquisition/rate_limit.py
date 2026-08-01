"""Simple rate limiting for controlled browser acquisition."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    """Enforce a minimum delay between browser requests."""

    min_interval_seconds: float = 2.0
    _last_request_at: float = field(default=0.0, init=False)

    def wait(self) -> None:
        """Sleep until the next request is allowed."""
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        self._last_request_at = time.monotonic()
