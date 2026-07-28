"""Architecture safety tests for product_identity package."""

from pathlib import Path

import pytest

MODULES = [
    "product_identity/__init__.py",
    "product_identity/adapter.py",
    "product_identity/config.py",
    "product_identity/demo.py",
    "product_identity/enums.py",
    "product_identity/evaluator.py",
    "product_identity/evidence.py",
    "product_identity/extractor.py",
    "product_identity/formatter.py",
    "product_identity/identifiers.py",
    "product_identity/models.py",
    "product_identity/normalization.py",
]

FORBIDDEN = (
    "import requests",
    "from requests",
    "import httpx",
    "import selenium",
    "import playwright",
    "import openai",
)


@pytest.mark.parametrize("relative_path", MODULES)
def test_product_identity_modules_forbid_network_and_ai(relative_path: str) -> None:
    source = (Path(__file__).resolve().parent.parent / relative_path).read_text(encoding="utf-8")
    lowered = source.lower()
    for token in FORBIDDEN:
        assert token not in lowered
