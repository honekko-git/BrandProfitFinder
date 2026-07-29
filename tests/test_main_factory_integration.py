"""CLI integration tests for main.py → factory → resolver → client wiring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
import openpyxl
import pytest

from config.constants import (
    MARKETPLACE_AMAZON_JP,
    MARKETPLACE_LOCAL,
    MARKETPLACE_RAKUTEN,
    MARKETPLACE_YAHOO,
    MARKETPLACE_YAHOO_AUCTION,
    SHEET_DOMESTIC_LISTINGS,
)
from marketplace.amazon_api_client import AmazonApiClient
from marketplace.amazon_client import FakeAmazonClient
from marketplace.amazon_marketplace import AmazonMarketplace
from marketplace.marketplace_factory import create_marketplace, get_all_marketplaces
from marketplace.rakuten_client import FakeRakutenClient, RakutenApiClient
from marketplace.rakuten_marketplace import RakutenMarketplace
from marketplace.yahoo_api_client import YahooApiClient
from marketplace.yahoo_marketplace import YahooMarketplace
from models.marketplace_search_result import SEARCH_SUCCESS
from utils.transport.models import TransportResponse

FIXTURES = Path(__file__).parent / "fixtures"

ACCESS_KEY = "AKIA_MAIN_FACTORY_KEY"
SECRET_KEY = "main-factory-secret-key"
PARTNER_TAG = "main-factory-partner"
RAKUTEN_APP_ID = "main-factory-rakuten-app"
RAKUTEN_ACCESS_KEY = "main-factory-rakuten-access"
YAHOO_CLIENT_ID = "main-factory-yahoo-client"


@pytest.fixture
def cli_output(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr("main.OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("main.EXCEL_FILENAME", "main_factory_integration.xlsx")
    return tmp_path


@pytest.fixture(autouse=True)
def _zero_transport_backoff(monkeypatch) -> None:
    monkeypatch.setenv("TRANSPORT_BACKOFF_BASE_SECONDS", "0")
    monkeypatch.setenv("TRANSPORT_BACKOFF_MAX_SECONDS", "0")


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _transport_response(payload: dict[str, Any]) -> TransportResponse:
    return TransportResponse(
        status_code=200,
        headers={"content-type": "application/json"},
        content=json.dumps(payload).encode("utf-8"),
        elapsed_seconds=0.01,
        retry_count=0,
    )


def _configure_live_env(monkeypatch) -> None:
    monkeypatch.setenv("RAKUTEN_APPLICATION_ID", RAKUTEN_APP_ID)
    monkeypatch.setenv("RAKUTEN_ACCESS_KEY", RAKUTEN_ACCESS_KEY)
    monkeypatch.setenv("RAKUTEN_API_ENABLED", "true")
    monkeypatch.setenv("RAKUTEN_API_DEMO_ENABLED", "false")
    monkeypatch.setenv("YAHOO_CLIENT_ID", YAHOO_CLIENT_ID)
    monkeypatch.setenv("YAHOO_API_ENABLED", "true")
    monkeypatch.setenv("AMAZON_ACCESS_KEY", ACCESS_KEY)
    monkeypatch.setenv("AMAZON_SECRET_KEY", SECRET_KEY)
    monkeypatch.setenv("AMAZON_PARTNER_TAG", PARTNER_TAG)
    monkeypatch.setenv("AMAZON_JP_ENABLED", "true")
    monkeypatch.setenv("AMAZON_JP_DEMO_ENABLED", "false")
    monkeypatch.setattr("main.RAKUTEN_API_ENABLED", True)
    monkeypatch.setattr("main.RAKUTEN_API_DEMO_ENABLED", False)
    monkeypatch.setattr("main.YAHOO_API_ENABLED", True)
    monkeypatch.setattr("main.AMAZON_JP_ENABLED", True)
    monkeypatch.setattr("main.AMAZON_JP_DEMO_ENABLED", False)
    monkeypatch.setattr("config.settings.RAKUTEN_APPLICATION_ID", RAKUTEN_APP_ID)
    monkeypatch.setattr("config.settings.RAKUTEN_ACCESS_KEY", RAKUTEN_ACCESS_KEY)
    monkeypatch.setattr("config.settings.RAKUTEN_API_ENABLED", True)
    monkeypatch.setattr("config.settings.RAKUTEN_API_DEMO_ENABLED", False)
    monkeypatch.setattr("config.settings.YAHOO_CLIENT_ID", YAHOO_CLIENT_ID)
    monkeypatch.setattr("config.settings.YAHOO_API_ENABLED", True)
    monkeypatch.setattr("config.settings.AMAZON_ACCESS_KEY", ACCESS_KEY)
    monkeypatch.setattr("config.settings.AMAZON_SECRET_KEY", SECRET_KEY)
    monkeypatch.setattr("config.settings.AMAZON_PARTNER_TAG", PARTNER_TAG)
    monkeypatch.setattr("config.settings.AMAZON_JP_ENABLED", True)
    monkeypatch.setattr("config.settings.AMAZON_JP_DEMO_ENABLED", False)


def _run_phase3_with_factory_spy(marketplace_name: str, monkeypatch):
    from main import run_phase3

    captured: dict[str, Any] = {}

    def _spy(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        captured["marketplace"] = create_marketplace(*args, **kwargs)
        return captured["marketplace"]

    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)
    with patch("main.create_marketplace", side_effect=_spy):
        output_path = run_phase3(marketplace_name=marketplace_name)

    return output_path, captured


# --- 1. CLI factory routing ---


def test_cli_rakuten_demo_routes_injected_fake_through_factory(cli_output, monkeypatch) -> None:
    monkeypatch.setattr("main.RAKUTEN_API_DEMO_ENABLED", True)

    output_path, captured = _run_phase3_with_factory_spy("rakuten", monkeypatch)

    assert output_path.exists()
    assert captured["args"][0] == "rakuten"
    assert isinstance(captured["kwargs"]["rakuten_client"], FakeRakutenClient)
    assert isinstance(captured["marketplace"], RakutenMarketplace)
    assert isinstance(captured["marketplace"]._client, FakeRakutenClient)


def test_cli_amazon_demo_routes_injected_fake_through_factory(cli_output, monkeypatch) -> None:
    monkeypatch.setattr("main.AMAZON_JP_DEMO_ENABLED", True)

    output_path, captured = _run_phase3_with_factory_spy("amazon_jp", monkeypatch)

    assert output_path.exists()
    assert captured["args"][0] == "amazon_jp"
    assert isinstance(captured["kwargs"]["amazon_client"], FakeAmazonClient)
    assert isinstance(captured["marketplace"], AmazonMarketplace)
    assert isinstance(captured["marketplace"]._client, FakeAmazonClient)


def test_cli_yahoo_routes_resolver_created_api_client(cli_output, monkeypatch) -> None:
    monkeypatch.setattr("main.YAHOO_API_ENABLED", True)
    monkeypatch.setattr("config.settings.YAHOO_CLIENT_ID", YAHOO_CLIENT_ID)
    monkeypatch.setattr("config.settings.YAHOO_API_ENABLED", True)

    payload = _fixture("yahoo_item_search_success.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))

    from main import run_phase3

    captured: dict[str, Any] = {}

    def _spy(*args, **kwargs):
        captured["kwargs"] = kwargs
        if args[0] == "yahoo":
            kwargs = dict(kwargs)
            kwargs["yahoo_client"] = YahooApiClient(
                settings=kwargs["yahoo_settings"],
                client=mock_client,
            )
        captured["marketplace"] = create_marketplace(*args, **kwargs)
        return captured["marketplace"]

    with patch("main.create_marketplace", side_effect=_spy):
        output_path = run_phase3(marketplace_name="yahoo")

    assert output_path.exists()
    assert captured["kwargs"].get("yahoo_client") is None
    assert isinstance(captured["marketplace"]._client, YahooApiClient)


# --- 2. Demo behavior regression ---


def test_cli_rakuten_demo_fixture_search_succeeds(cli_output, monkeypatch) -> None:
    monkeypatch.setattr("main.RAKUTEN_API_DEMO_ENABLED", True)

    output_path, captured = _run_phase3_with_factory_spy("rakuten", monkeypatch)
    marketplace = captured["marketplace"]

    from main import build_phase3_products

    results = [marketplace.search(product) for product in build_phase3_products()]
    assert all(result.status == SEARCH_SUCCESS for result in results)
    assert any(result.valid_listings for result in results)
    assert output_path.exists()

    workbook = openpyxl.load_workbook(output_path)
    sheet = workbook[SHEET_DOMESTIC_LISTINGS]
    assert sheet.max_row > 1


def test_cli_amazon_demo_fixture_search_succeeds(cli_output, monkeypatch) -> None:
    monkeypatch.setattr("main.AMAZON_JP_DEMO_ENABLED", True)

    output_path, captured = _run_phase3_with_factory_spy("amazon_jp", monkeypatch)
    marketplace = captured["marketplace"]

    from main import build_phase3_products

    results = [marketplace.search(product) for product in build_phase3_products()]
    assert all(result.status == SEARCH_SUCCESS for result in results)
    assert any(result.valid_listings for result in results)
    assert output_path.exists()


def test_cli_demo_clients_use_fixture_payload_not_empty_defaults(cli_output, monkeypatch) -> None:
    monkeypatch.setattr("main.RAKUTEN_API_DEMO_ENABLED", True)
    monkeypatch.setattr("main.AMAZON_JP_DEMO_ENABLED", True)

    _, rakuten_capture = _run_phase3_with_factory_spy("rakuten", monkeypatch)
    _, amazon_capture = _run_phase3_with_factory_spy("amazon_jp", monkeypatch)

    rakuten_payload = rakuten_capture["kwargs"]["rakuten_client"].payload
    amazon_payload = amazon_capture["kwargs"]["amazon_client"].payload

    assert rakuten_payload.get("Items")
    assert amazon_payload.get("items")


# --- 3. Live configuration behavior ---


def test_cli_live_rakuten_resolves_api_client(cli_output, monkeypatch) -> None:
    _configure_live_env(monkeypatch)

    output_path, captured = _run_phase3_with_factory_spy("rakuten", monkeypatch)

    assert output_path.exists()
    assert captured["args"][0] == "rakuten"
    assert captured["kwargs"]["rakuten_client"] is None
    assert isinstance(captured["marketplace"]._client, RakutenApiClient)


def test_cli_live_yahoo_resolves_api_client(cli_output, monkeypatch) -> None:
    _configure_live_env(monkeypatch)

    payload = _fixture("yahoo_item_search_success.json")
    transport_calls: list[str] = []

    def _recording_get(self, url, **kwargs):
        transport_calls.append("called")
        return _transport_response(payload)

    from main import run_phase3
    from utils.transport.transport import HttpTransport

    monkeypatch.setenv("YAHOO_USE_TRANSPORT", "true")
    monkeypatch.setattr("config.settings.YAHOO_USE_TRANSPORT", True)

    captured: dict[str, Any] = {}

    def _spy(*args, **kwargs):
        captured["marketplace"] = create_marketplace(*args, **kwargs)
        return captured["marketplace"]

    with patch("main.create_marketplace", side_effect=_spy), patch.object(HttpTransport, "get", _recording_get):
        output_path = run_phase3(marketplace_name="yahoo")

    assert output_path.exists()
    assert isinstance(captured["marketplace"]._client, YahooApiClient)
    assert transport_calls
    assert all(call == "called" for call in transport_calls)
    assert len(transport_calls) == 3


def test_cli_live_amazon_resolves_api_client(cli_output, monkeypatch) -> None:
    _configure_live_env(monkeypatch)

    output_path, captured = _run_phase3_with_factory_spy("amazon_jp", monkeypatch)

    assert output_path.exists()
    assert captured["args"][0] == "amazon_jp"
    assert captured["kwargs"]["amazon_client"] is None
    assert isinstance(captured["marketplace"]._client, AmazonApiClient)


# --- 4. Transport flag propagation ---


@pytest.mark.parametrize(
    ("marketplace_name", "transport_env", "settings_attr", "fixture_name", "http_method"),
    [
        ("rakuten", "RAKUTEN_USE_TRANSPORT", "RAKUTEN_USE_TRANSPORT", "rakuten_search_normal.json", "get"),
        ("yahoo", "YAHOO_USE_TRANSPORT", "YAHOO_USE_TRANSPORT", "yahoo_item_search_success.json", "get"),
        ("amazon_jp", "AMAZON_USE_TRANSPORT", "AMAZON_USE_TRANSPORT", "amazon_paapi_search_raw.json", "post"),
    ],
)
def test_cli_transport_flag_propagates_to_http_transport(
    cli_output,
    monkeypatch,
    marketplace_name: str,
    transport_env: str,
    settings_attr: str,
    fixture_name: str,
    http_method: str,
) -> None:
    _configure_live_env(monkeypatch)
    monkeypatch.setenv(transport_env, "true")
    monkeypatch.setattr(f"config.settings.{settings_attr}", True)

    payload = _fixture(fixture_name)
    transport_calls: list[str] = []

    def _recording_get(self, url, **kwargs):
        transport_calls.append("called")
        return _transport_response(payload)

    def _recording_post(self, url, **kwargs):
        transport_calls.append("called")
        return _transport_response(payload)

    from main import run_phase3
    from utils.transport.transport import HttpTransport

    patch_target = patch.object(HttpTransport, "get", _recording_get)
    if http_method == "post":
        patch_target = patch.object(HttpTransport, "post", _recording_post)

    with patch_target:
        output_path = run_phase3(marketplace_name=marketplace_name)

    assert output_path.exists()
    assert transport_calls
    assert all(call == "called" for call in transport_calls)
    assert len(transport_calls) == 3


# --- 5. No accidental live calls ---


def test_cli_local_run_makes_no_external_http_calls(cli_output, monkeypatch) -> None:
    from main import run_phase3
    from utils.transport.transport import HttpTransport

    monkeypatch.setattr("main.YAHOO_API_ENABLED", False)

    def _fail_get(self, url, **kwargs):
        raise AssertionError(f"Unexpected HttpTransport.get call: {url}")

    def _fail_post(self, url, **kwargs):
        raise AssertionError(f"Unexpected HttpTransport.post call: {url}")

    with patch.object(HttpTransport, "get", _fail_get), patch.object(HttpTransport, "post", _fail_post):
        output_path = run_phase3(marketplace_name="local")

    assert output_path.exists()


def test_cli_rakuten_without_demo_or_credentials_falls_back_without_http(cli_output, monkeypatch) -> None:
    from main import run_phase3
    from utils.transport.transport import HttpTransport

    monkeypatch.setattr("main.RAKUTEN_API_ENABLED", True)
    monkeypatch.setattr("main.RAKUTEN_API_DEMO_ENABLED", False)
    monkeypatch.setattr("config.settings.RAKUTEN_APPLICATION_ID", "")
    monkeypatch.setattr("config.settings.RAKUTEN_ACCESS_KEY", "")
    monkeypatch.setattr("config.settings.RAKUTEN_API_ENABLED", True)
    monkeypatch.setattr("config.settings.RAKUTEN_API_DEMO_ENABLED", False)

    captured: dict[str, Any] = {}

    def _spy(*args, **kwargs):
        captured["selected"] = args[0]
        return create_marketplace(*args, **kwargs)

    def _fail_get(self, url, **kwargs):
        raise AssertionError(f"Unexpected HttpTransport.get call: {url}")

    with patch("main.create_marketplace", side_effect=_spy), patch.object(HttpTransport, "get", _fail_get):
        output_path = run_phase3(marketplace_name="rakuten")

    assert output_path.exists()
    assert captured["selected"] == "local"


def test_cli_yahoo_without_client_id_falls_back_without_http(cli_output, monkeypatch) -> None:
    from main import run_phase3
    from utils.transport.transport import HttpTransport

    monkeypatch.setattr("main.YAHOO_API_ENABLED", True)
    monkeypatch.setattr("config.settings.YAHOO_CLIENT_ID", "")
    monkeypatch.setattr("config.settings.YAHOO_API_ENABLED", True)

    captured: dict[str, Any] = {}

    def _spy(*args, **kwargs):
        captured["selected"] = args[0]
        return create_marketplace(*args, **kwargs)

    def _fail_get(self, url, **kwargs):
        raise AssertionError(f"Unexpected HttpTransport.get call: {url}")

    with patch("main.create_marketplace", side_effect=_spy), patch.object(HttpTransport, "get", _fail_get):
        output_path = run_phase3(marketplace_name="yahoo")

    assert output_path.exists()
    assert captured["selected"] == "local"


# --- 6. Marketplace discovery ---


def test_resolve_marketplace_name_discovers_demo_and_live_targets(monkeypatch) -> None:
    from main import resolve_marketplace_name

    monkeypatch.setattr("main.RAKUTEN_API_ENABLED", True)
    monkeypatch.setattr("main.RAKUTEN_API_DEMO_ENABLED", True)
    assert resolve_marketplace_name(["--marketplace", "rakuten", "--demo-rakuten"]) == "rakuten"

    monkeypatch.setattr("main.RAKUTEN_API_ENABLED", False)
    monkeypatch.setattr("main.RAKUTEN_API_DEMO_ENABLED", False)
    monkeypatch.setattr("main.AMAZON_JP_ENABLED", True)
    monkeypatch.setattr("main.AMAZON_JP_DEMO_ENABLED", True)
    assert resolve_marketplace_name(["--marketplace", "amazon_jp", "--demo-amazon"]) == "amazon_jp"

    monkeypatch.setattr("main.AMAZON_JP_ENABLED", False)
    monkeypatch.setattr("main.AMAZON_JP_DEMO_ENABLED", False)
    monkeypatch.setattr("main.YAHOO_API_ENABLED", True)
    assert resolve_marketplace_name([]) == "yahoo"


def test_get_all_marketplaces_cli_discovery_has_no_http_and_usable_clients(monkeypatch) -> None:
    from utils.transport.transport import HttpTransport

    monkeypatch.setattr("config.settings.YAHOO_CLIENT_ID", YAHOO_CLIENT_ID)
    monkeypatch.setattr("config.settings.YAHOO_API_ENABLED", True)
    monkeypatch.setattr("config.settings.RAKUTEN_APPLICATION_ID", RAKUTEN_APP_ID)
    monkeypatch.setattr("config.settings.RAKUTEN_ACCESS_KEY", RAKUTEN_ACCESS_KEY)
    monkeypatch.setattr("config.settings.RAKUTEN_API_ENABLED", True)
    monkeypatch.setattr("config.settings.RAKUTEN_API_DEMO_ENABLED", True)
    monkeypatch.setattr("config.settings.AMAZON_JP_ENABLED", True)
    monkeypatch.setattr("config.settings.AMAZON_JP_DEMO_ENABLED", True)

    with patch.object(httpx.Client, "get") as httpx_get, patch.object(httpx.Client, "post") as httpx_post, patch.object(
        HttpTransport, "get"
    ) as transport_get, patch.object(HttpTransport, "post") as transport_post:
        marketplaces = get_all_marketplaces()

    names = {marketplace.marketplace_name for marketplace in marketplaces}
    assert names == {
        MARKETPLACE_LOCAL,
        MARKETPLACE_YAHOO,
        MARKETPLACE_AMAZON_JP,
        MARKETPLACE_RAKUTEN,
        MARKETPLACE_YAHOO_AUCTION,
    }
    by_name = {marketplace.marketplace_name: marketplace for marketplace in marketplaces}
    assert isinstance(by_name[MARKETPLACE_RAKUTEN]._client, FakeRakutenClient)
    assert isinstance(by_name[MARKETPLACE_AMAZON_JP]._client, FakeAmazonClient)
    assert isinstance(by_name[MARKETPLACE_YAHOO]._client, YahooApiClient)
    assert httpx_get.call_count == 0
    assert httpx_post.call_count == 0
    assert transport_get.call_count == 0
    assert transport_post.call_count == 0
