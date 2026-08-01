"""Create minimal Yahoo live DOM fixture from saved full page."""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

SOURCE = Path(__file__).resolve().parents[1] / "tests/fixtures/browser_acquisition/yahoo_live_ja.html"
TARGET = Path(__file__).resolve().parents[1] / "tests/fixtures/browser_acquisition/yahoo_live_dom_minimal.html"


def main() -> None:
    html = SOURCE.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")
    blocks: list[str] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href*='auctions.yahoo.co.jp/jp/auction/']"):
        href = anchor.get("href", "")
        match = re.search(r"/jp/auction/([a-z]\d+)", href, re.IGNORECASE)
        if not match or match.group(1) in seen:
            continue
        container = anchor.find_parent("li") or anchor.find_parent("div")
        if container is None:
            continue
        text = container.get_text(" ", strip=True)
        if "落札" not in text:
            continue
        seen.add(match.group(1))
        blocks.append(str(container))
        if len(blocks) >= 4:
            break

    minimal = (
        "<!DOCTYPE html><html lang='ja'><head><title>Yahoo Closed Search Minimal</title>"
        "<script type='application/ld+json'>"
        '{"@context":"https://schema.org","@type":"ItemList","itemListElement":['
        + ",".join(
            f'{{"@type":"ListItem","position":"{index}","url":"https://auctions.yahoo.co.jp/jp/auction/x{index}"}}'
            for index in range(1, len(blocks) + 1)
        )
        + "]}</script></head><body><ul>"
        + "".join(blocks)
        + "</ul></body></html>"
    )
    TARGET.write_text(minimal, encoding="utf-8")
    print("saved", TARGET, "blocks", len(blocks))


if __name__ == "__main__":
    main()
