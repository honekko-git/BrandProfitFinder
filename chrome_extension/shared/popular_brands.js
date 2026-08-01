/* Popular brand catalog loader (data-driven; no brand if/else navigation). */
(function (root) {
  root.BPF = root.BPF || {};
  const BRANDS_URL = "data/popular_brands.json";

  async function loadPopularBrands() {
    const response = await fetch(chrome.runtime.getURL(BRANDS_URL));
    if (!response.ok) {
      throw new Error("brand catalog unavailable");
    }
    const payload = await response.json();
    const rows = Array.isArray(payload.brands) ? payload.brands : [];
    return rows
      .filter((row) => row && row.enabled !== false)
      .map((row) => ({
        canonical_brand: String(row.canonical_brand || "").trim(),
        display_name: String(row.display_name || row.canonical_brand || "").trim(),
        fashionphile_search_term: String(
          row.fashionphile_search_term || row.canonical_brand || ""
        ).trim(),
        fashionphile_search_url: String(row.fashionphile_search_url || "").trim(),
        enabled: true,
      }))
      .filter((row) => row.canonical_brand && row.fashionphile_search_url);
  }

  function filterPopularBrands(brands, query) {
    const needle = String(query || "")
      .trim()
      .toLowerCase();
    if (!needle) return brands.slice();
    return brands.filter((item) => {
      return (
        item.display_name.toLowerCase().includes(needle) ||
        item.canonical_brand.toLowerCase().includes(needle) ||
        item.fashionphile_search_term.toLowerCase().includes(needle)
      );
    });
  }

  function resolveSelectedBrands(brands, selectedCanonicals) {
    const byName = {};
    brands.forEach((item) => {
      byName[item.canonical_brand] = item;
    });
    const out = [];
    const seen = new Set();
    (selectedCanonicals || []).forEach((name) => {
      const key = String(name || "").trim();
      if (!key || seen.has(key) || !byName[key]) return;
      seen.add(key);
      out.push(byName[key]);
    });
    return out;
  }

  function searchUrlForBrand(brand) {
    return brand && brand.fashionphile_search_url ? brand.fashionphile_search_url : "";
  }

  root.BPF.popularBrands = {
    loadPopularBrands,
    filterPopularBrands,
    resolveSelectedBrands,
    searchUrlForBrand,
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
