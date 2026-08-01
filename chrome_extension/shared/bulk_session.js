/* Bulk-acquisition session persistence (chrome.storage.local). */
(function (root) {
  root.BPF = root.BPF || {};
  const SESSION_KEY = "bpf_bulk_acquisition_session_v1";

  function nowIso() {
    return new Date().toISOString();
  }

  function sessionId() {
    const stamp = new Date()
      .toISOString()
      .replace(/[-:TZ.]/g, "")
      .slice(0, 14);
    return "bulk-" + stamp + "-" + Math.random().toString(16).slice(2, 8);
  }

  async function loadSession() {
    try {
      const stored = await chrome.storage.local.get([SESSION_KEY]);
      return stored[SESSION_KEY] || null;
    } catch (_err) {
      return null;
    }
  }

  async function saveSession(session) {
    session.last_updated_at = nowIso();
    await chrome.storage.local.set({ [SESSION_KEY]: session });
    return session;
  }

  async function clearSession() {
    await chrome.storage.local.remove([SESSION_KEY]);
  }

  function startSession(orderedBrands, extras) {
    if (!orderedBrands || !orderedBrands.length) {
      throw new Error("ブランドを選択してください");
    }
    extras = extras || {};
    const brands = {};
    orderedBrands.forEach((item, index) => {
      brands[item.canonical_brand] = {
        canonical_brand: item.canonical_brand,
        display_name: item.display_name,
        fashionphile_search_url: item.fashionphile_search_url,
        status: index === 0 ? "active" : "pending",
        detected_count: 0,
        imported_count: 0,
        already_imported_count: 0,
        remaining_count: 0,
        within_budget_count: 0,
        over_budget_count: 0,
        currency_unknown_count: 0,
        fx_unavailable_count: 0,
        workspace_batch_id: "",
        source_page_url: "",
        error_message: "",
        completed_at: "",
      };
    });
    const first = orderedBrands[0];
    return {
      session_id: extras.session_id || sessionId(),
      selected_brands: orderedBrands.map((item) => item.canonical_brand),
      brand_order: orderedBrands.map((item) => item.canonical_brand),
      current_brand_index: 0,
      current_brand: first.canonical_brand,
      completed_brands: [],
      status: "active",
      started_at: nowIso(),
      last_updated_at: nowIso(),
      workspace_batch_id: "",
      brands: brands,
      errors: [],
      user_message: "現在: " + first.display_name,
      budget_limit_jpy:
        extras.budget_limit_jpy === undefined || extras.budget_limit_jpy === null
          ? null
          : extras.budget_limit_jpy,
      budget_preset: extras.budget_preset || "none",
      fx_snapshot_id: extras.fx_snapshot_id || "",
      fx_summary: extras.fx_summary || {},
    };
  }

  function currentSearchUrl(session) {
    if (!session || !session.current_brand) return "";
    const progress = session.brands[session.current_brand];
    return progress ? progress.fashionphile_search_url : "";
  }

  function applyImportResult(session, result) {
    const brand = session.current_brand;
    const progress = session.brands[brand];
    const detected = Number(result.detected_count || 0);
    const remaining = Math.max(0, Number(result.remaining_count || 0));
    const already = Number(result.already_imported_count || 0);
    progress.detected_count = Math.max(progress.detected_count || 0, detected);
    progress.imported_count = Math.max(0, detected - remaining);
    progress.already_imported_count = already;
    progress.remaining_count = remaining;
    progress.within_budget_count = Math.max(
      progress.within_budget_count || 0,
      Number(result.within_budget_count || 0)
    );
    progress.over_budget_count = Math.max(
      progress.over_budget_count || 0,
      Number(result.over_budget_count || 0)
    );
    progress.currency_unknown_count = Math.max(
      progress.currency_unknown_count || 0,
      Number(result.currency_unknown_count || 0)
    );
    progress.fx_unavailable_count = Math.max(
      progress.fx_unavailable_count || 0,
      Number(result.fx_unavailable_count || 0)
    );
    progress.source_page_url = result.source_page_url || progress.source_page_url;
    if (result.workspace_batch_id) {
      progress.workspace_batch_id = result.workspace_batch_id;
      session.workspace_batch_id = result.workspace_batch_id;
    }
    progress.status = "importing";
    if (remaining === 0 && detected > 0) {
      progress.status = "visible_complete";
      progress.completed_at = nowIso();
      if (session.completed_brands.indexOf(brand) < 0) {
        session.completed_brands.push(brand);
      }
      session.user_message =
        progress.display_name + ": 現在表示されている商品をすべて取り込みました。";
    } else if (remaining > 0) {
      session.user_message =
        progress.display_name +
        ": " +
        progress.imported_count +
        "件取込済 / 残り" +
        remaining +
        "件";
    }
    return session;
  }

  function markFailed(session, message) {
    const progress = session.brands[session.current_brand];
    progress.status = "failed";
    progress.error_message = message;
    session.status = "failed";
    session.errors.push(progress.canonical_brand + ": " + message);
    session.user_message = message;
    return session;
  }

  function retryFailed(session) {
    const progress = session.brands[session.current_brand];
    if (!progress || progress.status !== "failed") return session;
    progress.status = "active";
    progress.error_message = "";
    session.status = "active";
    session.user_message = "現在: " + progress.display_name;
    return session;
  }

  function advanceNext(session) {
    const current = session.brands[session.current_brand];
    if (
      current &&
      current.remaining_count === 0 &&
      current.detected_count > 0 &&
      current.status !== "skipped"
    ) {
      current.status = "visible_complete";
      if (session.completed_brands.indexOf(session.current_brand) < 0) {
        session.completed_brands.push(session.current_brand);
      }
    }
    const nextIndex = session.current_brand_index + 1;
    if (nextIndex >= session.brand_order.length) {
      session.status = "complete";
      session.current_brand = "";
      session.user_message = "選択したブランドの取り込みが完了しました。";
      return session;
    }
    session.current_brand_index = nextIndex;
    session.current_brand = session.brand_order[nextIndex];
    session.brands[session.current_brand].status = "active";
    session.status = "active";
    session.user_message = "現在: " + session.brands[session.current_brand].display_name;
    return session;
  }

  function skipCurrent(session) {
    const progress = session.brands[session.current_brand];
    progress.status = "skipped";
    progress.completed_at = nowIso();
    return advanceNext(session);
  }

  function pauseSession(session) {
    session.status = "paused";
    session.user_message = "一括取得を一時停止しました。";
    return session;
  }

  function resumeSession(session) {
    if (session.status === "complete") return session;
    session.status = "active";
    const current = session.brands[session.current_brand];
    session.user_message = current ? "現在: " + current.display_name : "一括取得を再開しました。";
    return session;
  }

  function endSession(session) {
    session.status = "ended";
    session.user_message = "一括取得を終了しました。";
    return session;
  }

  function completedCount(session) {
    return session.brand_order.filter((name) => {
      const status = session.brands[name].status;
      return status === "visible_complete" || status === "skipped";
    }).length;
  }

  root.BPF.bulkSession = {
    SESSION_KEY,
    loadSession,
    saveSession,
    clearSession,
    startSession,
    currentSearchUrl,
    applyImportResult,
    markFailed,
    retryFailed,
    advanceNext,
    skipCurrent,
    pauseSession,
    resumeSession,
    endSession,
    completedCount,
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
