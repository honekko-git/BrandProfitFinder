/* Fashionphile hostname / URL / price validation shared by content + popup. */
(function (root) {
  const PRODUCT_PATH = /\/products\/[^/?#]+/i;
  const SEARCH_OR_CATEGORY = /\/(search|collections|pages|cart|account|blogs)\b/i;
  const TRACKING_KEYS = new Set([
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "_pos",
    "_sid",
    "_ss",
    "variant",
  ]);

  function isFashionphileHostname(hostname) {
    const host = String(hostname || "").toLowerCase().replace(/^www\./, "");
    return host === "fashionphile.com";
  }

  function isProductUrl(url) {
    try {
      const parsed = new URL(url, "https://www.fashionphile.com");
      if (!isFashionphileHostname(parsed.hostname)) return false;
      if (!PRODUCT_PATH.test(parsed.pathname)) return false;
      if (SEARCH_OR_CATEGORY.test(parsed.pathname) && !PRODUCT_PATH.test(parsed.pathname)) return false;
      return true;
    } catch (_err) {
      return false;
    }
  }

  function canonicalizeProductUrl(url) {
    const parsed = new URL(url, "https://www.fashionphile.com");
    if (!isFashionphileHostname(parsed.hostname)) {
      throw new Error("invalid host");
    }
    const match = parsed.pathname.match(PRODUCT_PATH);
    if (!match) throw new Error("not product");
    parsed.protocol = "https:";
    parsed.hostname = "www.fashionphile.com";
    parsed.pathname = match[0].replace(/\/+$/, "");
    parsed.hash = "";
    const kept = [];
    parsed.searchParams.forEach((value, key) => {
      if (!TRACKING_KEYS.has(key.toLowerCase())) kept.push([key, value]);
    });
    parsed.search = "";
    kept.forEach(([key, value]) => parsed.searchParams.append(key, value));
    // Drop remaining query for stable identity; product handle is enough.
    parsed.search = "";
    return parsed.toString().replace(/\/$/, "");
  }

  function parsePriceText(text) {
    const raw = String(text || "").replace(/\s+/g, " ").trim();
    if (!raw) return null;
    // Ignore installment / monthly teasers.
    if (/\/\s*mo|per\s*month|月々|installment/i.test(raw)) return null;
    let currency = null;
    if (raw.includes("$") || /USD/i.test(raw)) currency = "USD";
    else if (raw.includes("€") || /EUR/i.test(raw)) currency = "EUR";
    else if (raw.includes("£") || /GBP/i.test(raw)) currency = "GBP";
    else if (raw.includes("¥") || /JPY|円/i.test(raw)) currency = "JPY";
    const numeric = raw.replace(/[^0-9.,]/g, "");
    if (!numeric) return null;
    let normalized = numeric;
    if (normalized.includes(",") && normalized.includes(".")) {
      normalized = normalized.replace(/,/g, "");
    } else if (normalized.includes(",") && !normalized.includes(".")) {
      // $1,295 style
      if (/,\d{2}$/.test(normalized)) normalized = normalized.replace(",", ".");
      else normalized = normalized.replace(/,/g, "");
    }
    const value = Number.parseFloat(normalized);
    if (!Number.isFinite(value) || value <= 0) return null;
    return { amount: value, currency, formatted: raw };
  }

  root.BPF = root.BPF || {};
  root.BPF.validation = {
    isFashionphileHostname,
    isProductUrl,
    canonicalizeProductUrl,
    parsePriceText,
    PRODUCT_PATH,
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
