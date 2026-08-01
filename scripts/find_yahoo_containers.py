"""Find Yahoo listing container patterns."""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

HTML = Path(__file__).resolve().parents[1] / "tests/fixtures/browser_acquisition/yahoo_live_ja.html"


def main() -> None:
    html = HTML.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    # Find anchors with auction URLs that have 落札 in ancestor
    count = 0
    for anchor in soup.select("a[href*='auctions.yahoo.co.jp/jp/auction/']"):
        href = anchor.get("href", "")
        if not re.search(r"/jp/auction/[a-z]\d+", href):
            continue
        container = _find_listing_container(anchor)
        if container is None:
            continue
        text = container.get_text(" ", strip=True)
        if "落札" not in text:
            continue
        title = _extract_title(anchor, container)
        price = _extract_rakusatsu_price(text)
        if price is None:
            continue
        count += 1
        if count <= 10:
            print(count, price, title[:80])
            print("  url", href)
    print("total sold", count)


def _find_listing_container(anchor):
    for parent in anchor.parents:
        if parent.name in {"li", "article", "section"}:
            return parent
        classes = " ".join(parent.get("class", []))
        if any(token in classes.lower() for token in ("item", "product", "result", "listing")):
            return parent
        text = parent.get_text(" ", strip=True)
        if "落札" in text and len(text) < 500:
            return parent
    return anchor.find_parent("div")


def _extract_title(anchor, container) -> str:
    for node in container.select("a[href*='auctions.yahoo.co.jp/jp/auction/']"):
        text = node.get_text(" ", strip=True)
        if len(text) > 10:
            return text
    return anchor.get_text(" ", strip=True) or container.get_text(" ", strip=True)[:120]


def _extract_rakusatsu_price(text: str) -> int | None:
    match = re.search(r"落札\s*([\d,]+)\s*円", text)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


if __name__ == "__main__":
    main()
