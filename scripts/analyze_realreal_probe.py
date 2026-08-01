"""Analyze RealReal probe HTML for product card structure."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

html = Path("output/realreal_probe.html").read_text(encoding="utf-8")
soup = BeautifulSoup(html, "lxml")
testids = Counter()
for node in soup.select("[data-testid]"):
    testids[node.get("data-testid")] += 1
print("top testids", testids.most_common(30))

# Find a product link with nearby price
for link in soup.select("a[href*='/products/women/']"):
    href = link.get("href") or ""
    if href.count("/") < 4:
        continue
    parent = link
    for _ in range(6):
        if parent.parent is None:
            break
        parent = parent.parent
        text = " ".join(parent.get_text(" ", strip=True).split())
        if "$" in text and len(text) > 20:
            print("href", href)
            print("text", text[:300])
            print("parent classes", parent.get("class"))
            print("parent testid", parent.get("data-testid"))
            print("html snippet", str(parent)[:600])
            raise SystemExit(0)
print("no priced parent found")
