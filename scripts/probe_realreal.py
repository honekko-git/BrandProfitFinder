"""Probe The RealReal search page structure."""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from marketplace.browser_acquisition.browser_session import BrowserSession

url = "https://www.therealreal.com/products?keywords=chanel+wallet"
print("fetch", url)
result = BrowserSession(timeout_ms=45000).fetch_html(
    url,
    wait_selector="a[href*='/products/'], [data-testid], .product-card, .ProductCard",
)
print("status", result.status_code, "blocked", result.blocked_reason, "len", len(result.html))
Path("output/realreal_probe.html").write_text(result.html, encoding="utf-8")
soup = BeautifulSoup(result.html, "lxml")
print("title", (soup.title.string if soup.title else "")[:100])
for sel in (
    "a[href*='/products/']",
    "[data-testid]",
    "[data-product-id]",
    ".product-card",
    ".ProductCard",
    "article",
):
    print(sel, len(soup.select(sel)))
hrefs = [a.get("href") for a in soup.select("a[href*='/products/']")[:15]]
print("hrefs", hrefs[:10])
print("captcha", "captcha" in result.html.lower(), "grecaptcha", "grecaptcha" in result.html.lower())
# sample text near first product link
if hrefs:
    link = soup.select_one("a[href*='/products/']")
    parent = link.find_parent(["div", "li", "article"]) if link else None
    print("sample text", " ".join((parent or link).get_text(" ", strip=True).split())[:250])
