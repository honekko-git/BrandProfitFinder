"""Yahoo Auction live connector configuration."""

from __future__ import annotations

from enum import StrEnum


class TransportMode(StrEnum):
    """Domestic market transport selection for Yahoo Auction."""

    FIXTURE = "fixture"
    LIVE = "live"
