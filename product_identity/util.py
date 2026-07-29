"""Shared deterministic helpers for product identity packages.

Example::

    from product_identity.util import stable_unique

    warnings = stable_unique(["a", "b", "a"])  # ["a", "b"]
"""

from __future__ import annotations


def stable_unique(values: list[str]) -> list[str]:
    """Return de-duplicated strings preserving first-seen order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
