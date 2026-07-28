"""Architecture safety tests for GOAT marketplace foundation."""

from pathlib import Path

import pytest

GOAT_MODULES = [
    "marketplace/goat_client.py",
    "marketplace/goat_marketplace.py",
    "marketplace/goat_response_parser.py",
    "marketplace/goat_settings.py",
    "marketplace/goat_exceptions.py",
]

FORBIDDEN_IMPORTS = (
    "import requests",
    "from requests",
    "import httpx",
    "from httpx",
    "import selenium",
    "from selenium",
    "import playwright",
    "from playwright",
)


@pytest.mark.parametrize("relative_path", GOAT_MODULES)
def test_goat_modules_forbid_network_clients(relative_path: str) -> None:
    source = (Path(__file__).resolve().parent.parent / relative_path).read_text(encoding="utf-8")
    lowered = source.lower()
    for token in FORBIDDEN_IMPORTS:
        assert token not in lowered


def test_fake_client_docstring_identifies_synthetic_fixtures() -> None:
    from marketplace.goat_client import FakeGoatClient

    doc = FakeGoatClient.__doc__ or ""
    assert "synthetic" in doc.lower()
    assert "official" in doc.lower()


def test_fixture_identifies_internal_format() -> None:
    import json

    payload = json.loads(
        (Path(__file__).parent / "fixtures" / "goat_search_normal.json").read_text(encoding="utf-8")
    )
    item = payload["items"][0]
    metadata = item.get("metadata", {})
    assert metadata.get("source_format") == "brandprofitfinder_internal_fixture"
    assert "Synthetic" in metadata.get("fixture_note", "")
