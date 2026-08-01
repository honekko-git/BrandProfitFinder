# BrandProfitFinder Chrome Extension (Fashionphile)

Bulk-import **currently visible** Fashionphile search results into your local BrandProfitFinder app.

## What this does

1. You open Fashionphile in normal Chrome and search (e.g. PRADA).
2. Products render in the page as usual.
3. You click the BrandProfitFinder extension → **現在の検索結果を一括取込**.
4. Visible product cards are sent to `http://127.0.0.1:8000`.
5. BrandProfitFinder imports them, runs the existing Yahoo! Auctions + Mercari + profit path, and opens the workspace.

This extension does **not**:

- bypass CAPTCHA, login, or access controls
- purchase, checkout, pay, or negotiate
- auto-scroll or scrape private APIs
- send data to any remote server other than your local BrandProfitFinder

## Prerequisites

1. BrandProfitFinder running locally:

```bash
python main.py web
```

Open `http://127.0.0.1:8000` to confirm the app is up.

2. Google Chrome (or Chromium) with Developer mode available.

## Install (unpacked)

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select this folder:

```text
chrome_extension
```

(full path example: `C:\Users\...\BrandProfitFinder\chrome_extension`)

5. Pin the extension if desired.

## Use

1. Start BrandProfitFinder (`python main.py web`).
2. Open [Fashionphile](https://www.fashionphile.com) in Chrome.
3. Search for a brand (e.g. `PRADA` or `Louis Vuitton`).
4. Wait until product cards are visible.
5. If the page shows a human challenge, complete it yourself first.
6. Scroll normally if you want more lazy-loaded cards included (only currently rendered cards are captured).
7. Click the BrandProfitFinder extension icon.
8. Click **現在の検索結果を一括取込**.
9. Click **ワークスペースを開く** (or open the shown batch URL).

## Notes

- Only **Fashionphile** is supported in Version 1.0 of the extension.
- Exact Fashionphile product URLs are preserved and used as acquisition links.
- Yahoo! Auctions and Mercari remain the only domestic comparable sources.
- Automatic profit analysis is capped (first eligible products) to keep local load bounded; remaining imported candidates can be analyzed from the workspace.
- If more than 80 valid products are visible, the extension asks before import and sends only the first 80 (deterministic page order). This is informational, not an error.
- The Fashionphile tab is not redirected away from your search.

## Local development security

The capture endpoint is:

`POST http://127.0.0.1:8000/acquisition-workspace/import/browser-capture`

- Bound to localhost by the web server.
- Requires header `X-BrandProfitFinder-Capture: 1`.
- CORS allowlist is limited to `chrome-extension://…` origins for this path only.
- Marketplace must be Fashionphile; product URLs are re-validated server-side.

Unpacked extension IDs change per machine; therefore the allowlist matches the `chrome-extension://` scheme rather than a single fixed ID during local development.
