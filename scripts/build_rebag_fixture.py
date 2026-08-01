"""Build Rebag search fixture from live probe HTML."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

probe = Path("output/rebag_probe.html").read_text(encoding="utf-8")
soup = BeautifulSoup(probe, "lxml")
seen: set[str] = set()
cards = []
for node in soup.select("div.plp__product[data-product-id], div.plp-product[data-product-id]"):
    link = node.select_one("a[href*='/products/']")
    if link is None:
        continue
    href = (link.get("href") or "").strip()
    if not href or href in seen:
        continue
    seen.add(href)
    cards.append(node)
    if len(cards) >= 24:
        break

out = Path("tests/fixtures/browser_acquisition/rebag_search_results.html")
parts = [
    "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>",
    "<title>Rebag Search Fixture</title></head><body>",
]
for card in cards:
    parts.append(str(card))
parts.append("</body></html>")
out.write_text("\n".join(parts), encoding="utf-8")
print("wrote", out, "cards", len(cards))
for card in cards[:8]:
    text = " ".join(card.get_text(" ", strip=True).split())
    print(text[:100])

# empty fixture
Path("tests/fixtures/browser_acquisition/rebag_empty.html").write_text(
    "<!DOCTYPE html><html><head><title>Rebag Empty</title></head><body><div>No products</div></body></html>",
    encoding="utf-8",
)
# captcha challenge fixture (no products)
Path("tests/fixtures/browser_acquisition/rebag_captcha.html").write_text(
    "<!DOCTYPE html><html><head><title>Verify</title></head>"
    "<body><h1>Verify you are human</h1><div class='captcha'>captcha challenge</div></body></html>",
    encoding="utf-8",
)
