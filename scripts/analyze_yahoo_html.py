"""Analyze saved Yahoo live HTML."""

from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

HTML = Path(__file__).resolve().parents[1] / "tests/fixtures/browser_acquisition/yahoo_live_ja.html"


def main() -> None:
    html = HTML.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    for index, script in enumerate(soup.select("script[type='application/ld+json']")):
        raw = script.string or script.get_text()
        try:
            data = json.loads(raw)
            print(f"JSONLD {index} keys:", data.keys() if isinstance(data, dict) else type(data))
            print(str(data)[:800])
        except json.JSONDecodeError as exc:
            print("JSONLD err", exc)

    links = soup.select("a[href*='auctions.yahoo.co.jp/jp/auction/']")[:8]
    for anchor in links:
        print("LINK", anchor.get("href"))
        print(" TEXT", anchor.get_text(" ", strip=True)[:100])
        parent = anchor.find_parent("li") or anchor.find_parent("article") or anchor.find_parent("div", recursive=False)
        if parent is not None:
            print(" PARENT", parent.get_text(" ", strip=True)[:200])
        print("---")

    prices = re.findall(r"([\d,]+)\s*円", html)
    print("price count", len(prices), "sample", prices[:15])
    print("落札 count", html.count("落札"))

    # Find elements near 落札
    for node in soup.find_all(string=re.compile("落札")):
        parent = node.find_parent(["li", "div", "article"])
        if parent is not None:
            text = parent.get_text(" ", strip=True)
            if "シャネル" in text or "CHANEL" in text:
                print("SOLD NODE", text[:250])
                break


if __name__ == "__main__":
    main()
