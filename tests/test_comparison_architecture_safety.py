"""Architecture safety tests for comparison package."""

from pathlib import Path

import pytest

COMPARISON_MODULES = [
    "comparison/config.py",
    "comparison/currency_safety.py",
    "comparison/demo_providers.py",
    "comparison/engine.py",
    "comparison/formatter.py",
    "comparison/matcher.py",
    "comparison/models.py",
    "comparison/ranking.py",
    "comparison/service.py",
    "comparison/util.py",
]

FORBIDDEN = (
    "import requests",
    "from requests",
    "import httpx",
    "from httpx",
    "import selenium",
    "from selenium",
    "import playwright",
    "from playwright",
)


@pytest.mark.parametrize("relative_path", COMPARISON_MODULES)
def test_comparison_modules_forbid_network_clients(relative_path: str) -> None:
    source = (Path(__file__).resolve().parent.parent / relative_path).read_text(encoding="utf-8")
    lowered = source.lower()
    for token in FORBIDDEN:
        assert token not in lowered
