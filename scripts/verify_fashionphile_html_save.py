"""Verify Fashionphile browser-DOM HTML against the current parser."""

from __future__ import annotations

import json
from pathlib import Path

from marketplace.browser_acquisition.fashionphile_acquirer import parse_fashionphile_html

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(
    r"C:\Users\メイン\.cursor\browser-logs"
    r"\cdp-response-Runtime.evaluate-2026-07-31T14-12-05-209Z.json"
)
OUT = ROOT / "output" / "fashionphile_prada_browser_dom.html"
REPORT = ROOT / "output" / "fashionphile_html_save_verification.json"


def main() -> None:
    payload = json.loads(SRC.read_text(encoding="utf-8"))
    html = payload["result"]["value"]
    OUT.write_text(html, encoding="utf-8")
    listings = parse_fashionphile_html(html)
    shell = (
        "<!DOCTYPE html><html><head><title>Search</title></head>"
        '<body><div id="root"></div><script src="/app.js"></script></body></html>'
    )
    report = {
        "source": "browser DOM outerHTML (user-visible page after render)",
        "saved_path": str(OUT),
        "bytes": OUT.stat().st_size,
        "products_path_count": html.count("/products/"),
        "legacy_p_path_count": html.count("/p/"),
        "hcaptcha_markers_present": "hcaptcha" in html.lower(),
        "parsed_by_current_parser": len(listings),
        "sample_parsed": [
            {"title": item.title[:80], "url": item.url, "price": str(item.price)}
            for item in listings[:5]
        ],
        "empty_spa_shell_parsed": len(parse_fashionphile_html(shell)),
        "conclusion": (
            "A fully rendered browser DOM (~1.3MB) can be parsed and uploaded, "
            "but obtaining that file through normal Chrome 'Save Page As' is not "
            "operationally reliable on Fashionphile (SPA + hCaptcha markers; user "
            "reports save cancelled). Empty SPA shell HTML yields 0 products. "
            "HTML upload is therefore not the Version 1.0 CAPTCHA workaround."
        ),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
