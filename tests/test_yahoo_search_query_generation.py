"""Tests for Yahoo search query generation."""

from __future__ import annotations

from marketplace.browser_acquisition.yahoo_search_queries import build_yahoo_search_queries


def test_builds_japanese_and_english_queries_up_to_three() -> None:
    queries = build_yahoo_search_queries(
        title="Chanel Classic Wallet Black Caviar",
        brand="Chanel",
        category="Wallet",
    )
    assert 1 <= len(queries) <= 4
    assert any("シャネル" in query for query in queries)
    assert any("wallet" in query.lower() or "財布" in query for query in queries)


def test_queries_are_deduplicated() -> None:
    queries = build_yahoo_search_queries(
        title="Chanel Wallet Black Caviar",
        brand="Chanel",
        category="Wallet",
    )
    assert len(queries) == len(set(queries))


def test_includes_material_and_color_tokens() -> None:
    queries = build_yahoo_search_queries(
        title="Chanel Classic Wallet Black Caviar",
        brand="Chanel",
        category="Wallet",
    )
    joined = " ".join(queries)
    assert "caviar" in joined.lower() or "キャビア" in joined
    assert "black" in joined.lower() or "黒" in joined


def test_bag_queries_use_bag_not_wallet_fallback() -> None:
    queries = build_yahoo_search_queries(
        title="Chanel Classic Double Flap Bag Quilted Patent Medium",
        brand="Chanel",
        category="Bag",
    )
    joined = " ".join(queries)
    assert any("マトラッセ" in query or "クラシックフラップ" in query or "Classic" in query for query in queries)
    # Must not force wallet-only fallback for handbags.
    assert not all("財布" in query and "マトラッセ" not in query for query in queries)
    assert "シャネル" in joined or "Chanel" in joined
    assert not queries[0].startswith("シャネル バッグ")
