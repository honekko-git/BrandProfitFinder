document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector(".search-form");
    if (form) {
        form.addEventListener("submit", () => {
            const button = form.querySelector("button[type='submit']");
            if (button) {
                button.disabled = true;
                button.textContent = "検索中...";
            }
        });
    }

    document.querySelectorAll("[data-live-acquisition-form]").forEach((liveForm) => {
        liveForm.addEventListener("submit", () => {
            const button = liveForm.querySelector("button[type='submit']");
            const status = liveForm.querySelector(".intake-run-status");
            if (button) {
                button.disabled = true;
                button.textContent = "Searching...";
            }
            if (status) {
                status.textContent = "Searching... Retrieving... Parsing...";
            }
        });
    });

    document.querySelectorAll("[data-operational-profit-form]").forEach((profitForm) => {
        profitForm.addEventListener("submit", () => {
            const button = profitForm.querySelector("button[type='submit']");
            if (button) {
                button.disabled = true;
                button.textContent = "Analyzing...";
            }
        });
    });

    const rowsContainer = document.getElementById("manual-rows");
    const addButton = document.getElementById("add-manual-row");
    if (rowsContainer && addButton) {
        const maxIndex = Number(rowsContainer.dataset.maxIndex || "10");

        addButton.addEventListener("click", () => {
            const nextIndex = Number(rowsContainer.dataset.nextIndex || "0");
            if (nextIndex >= maxIndex) {
                addButton.disabled = true;
                addButton.textContent = "入力欄は上限です";
                return;
            }

            const row = document.createElement("div");
            row.className = "manual-row";
            row.innerHTML = `
                <input name="title_${nextIndex}" placeholder="商品名">
                <input name="price_${nextIndex}" placeholder="価格">
                <input name="currency_${nextIndex}" placeholder="通貨" value="USD">
                <input name="url_${nextIndex}" placeholder="URL">
                <input name="source_${nextIndex}" placeholder="仕入先" value="Manual">
            `;
            rowsContainer.appendChild(row);
            rowsContainer.dataset.nextIndex = String(nextIndex + 1);

            if (nextIndex + 1 >= maxIndex) {
                addButton.disabled = true;
                addButton.textContent = "入力欄は上限です";
            }
        });
    }

    document.querySelectorAll("details[data-persist-key]").forEach((details) => {
        const key = details.dataset.persistKey;
        if (!key) {
            return;
        }
        try {
            if (sessionStorage.getItem(key) === "open") {
                details.open = true;
            }
        } catch (_error) {
            // sessionStorage may be unavailable; keep default collapsed state
        }
        details.addEventListener("toggle", () => {
            try {
                sessionStorage.setItem(key, details.open ? "open" : "closed");
            } catch (_error) {
                // ignore persistence failures
            }
        });
    });

    const rankingScrollKey = "acquisition-workspace-ranking-scroll";
    document.querySelectorAll("[data-save-ranking-scroll]").forEach((link) => {
        link.addEventListener("click", () => {
            try {
                sessionStorage.setItem(rankingScrollKey, String(window.scrollY || 0));
            } catch (_error) {
                // ignore
            }
        });
    });

    if (document.querySelector("[data-ranking-scroll-root]")) {
        try {
            const saved = sessionStorage.getItem(rankingScrollKey);
            if (saved !== null) {
                const y = Number(saved);
                if (!Number.isNaN(y)) {
                    window.scrollTo(0, y);
                }
                sessionStorage.removeItem(rankingScrollKey);
            }
        } catch (_error) {
            // ignore
        }
    }

    const workflowFilterKey = "acquisition-workspace-workflow-filter";

    function applyOpsFilters() {
        const budgetSelect = document.querySelector("[data-budget-filter]");
        const brandSelect = document.querySelector("[data-brand-filter]");
        const budget = budgetSelect ? budgetSelect.value : "unlimited";
        const brand = brandSelect ? brandSelect.value : "all";
        const rows = document.querySelectorAll("[data-ops-ranking-table] tbody tr[data-candidate-id]");
        let visible = 0;
        rows.forEach((row) => {
            const workflowHidden = row.getAttribute("data-workflow-hidden") === "1";
            const purchase = Number(row.getAttribute("data-purchase-jpy") || "0");
            const rowBrand = row.getAttribute("data-brand") || "";
            const budgetOk = budget === "unlimited" || purchase <= Number(budget);
            const brandOk = brand === "all" || rowBrand === brand;
            const show = !workflowHidden && budgetOk && brandOk;
            row.style.display = show ? "" : "none";
            if (show) {
                visible += 1;
            }
        });
        const empty = document.querySelector("[data-ops-filter-empty]");
        if (empty) {
            empty.hidden = visible > 0 || rows.length === 0;
        }
    }

    function applyWorkflowFilter(filterCode) {
        const code = filterCode || "all";
        const rows = document.querySelectorAll("[data-workflow-ranking-table] tbody tr[data-workflow-status]");
        let visible = 0;
        rows.forEach((row) => {
            const status = row.getAttribute("data-workflow-status") || "unchecked";
            const show = code === "all" || status === code;
            row.setAttribute("data-workflow-hidden", show ? "0" : "1");
            if (show) {
                visible += 1;
            }
        });
        const empty = document.querySelector("[data-workflow-filter-empty]");
        if (empty) {
            empty.hidden = visible > 0 || rows.length === 0;
        }
        document.querySelectorAll("[data-workflow-filter]").forEach((chip) => {
            chip.classList.toggle("is-active", chip.getAttribute("data-workflow-filter") === code);
        });
        try {
            sessionStorage.setItem(workflowFilterKey, code);
            const url = new URL(window.location.href);
            if (code === "all") {
                url.searchParams.delete("status");
            } else {
                url.searchParams.set("status", code);
            }
            window.history.replaceState({}, "", url.toString());
        } catch (_error) {
            // ignore
        }
        applyOpsFilters();
    }

    const initialFilterChip = document.querySelector("[data-workflow-filter].is-active");
    let initialFilter = initialFilterChip
        ? initialFilterChip.getAttribute("data-workflow-filter")
        : "all";
    try {
        const savedFilter = sessionStorage.getItem(workflowFilterKey);
        if (savedFilter && document.querySelector(`[data-workflow-filter="${savedFilter}"]`)) {
            initialFilter = savedFilter;
        }
    } catch (_error) {
        // ignore
    }
    if (document.querySelector("[data-workflow-ranking-table]")) {
        applyWorkflowFilter(initialFilter);
    } else if (document.querySelector("[data-ops-ranking-table]")) {
        applyOpsFilters();
    }
    document.querySelectorAll("[data-workflow-filter]").forEach((chip) => {
        chip.addEventListener("click", () => {
            applyWorkflowFilter(chip.getAttribute("data-workflow-filter") || "all");
        });
    });

    document.querySelectorAll("[data-budget-filter], [data-brand-filter]").forEach((select) => {
        select.addEventListener("change", applyOpsFilters);
    });

    function syncWorkflowBadges(candidateId, workflow) {
        document.querySelectorAll(`[data-candidate-id="${candidateId}"]`).forEach((root) => {
            if (root.matches("tr[data-workflow-status]")) {
                root.setAttribute("data-workflow-status", workflow.status);
            }
            root.querySelectorAll("[data-component='StatusBadge']").forEach((badge) => {
                badge.textContent = workflow.label;
                badge.setAttribute("data-status", workflow.status);
                badge.className = `workflow-status-badge ${workflow.css_class}`;
            });
            root.querySelectorAll("[data-workflow-status-select]").forEach((select) => {
                if (select.value !== workflow.status) {
                    select.value = workflow.status;
                }
            });
        });
        document.querySelectorAll(`[data-workflow-status-select][data-candidate-id="${candidateId}"]`).forEach((select) => {
            select.value = workflow.status;
            const cell = select.closest("[data-candidate-id], .sourcing-detail-page, .ranking-workflow-cell, .sourcing-workflow-bar");
            const scope = cell || document;
            scope.querySelectorAll("[data-component='StatusBadge']").forEach((badge) => {
                if (badge.closest(`[data-candidate-id="${candidateId}"]`) || document.getElementById("sourcing-detail")) {
                    badge.textContent = workflow.label;
                    badge.setAttribute("data-status", workflow.status);
                    badge.className = `workflow-status-badge ${workflow.css_class}`;
                }
            });
        });
        const detail = document.getElementById("sourcing-detail");
        if (detail && detail.getAttribute("data-candidate-id") === candidateId) {
            detail.querySelectorAll("[data-component='StatusBadge']").forEach((badge) => {
                badge.textContent = workflow.label;
                badge.setAttribute("data-status", workflow.status);
                badge.className = `workflow-status-badge ${workflow.css_class}`;
            });
        }
        const active = document.querySelector("[data-workflow-filter].is-active");
        if (active) {
            applyWorkflowFilter(active.getAttribute("data-workflow-filter") || "all");
        } else {
            applyOpsFilters();
        }
    }

    async function saveWorkflow(candidateId, payload) {
        const response = await fetch(`/acquisition-workspace/workflow/${encodeURIComponent(candidateId)}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
            },
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            throw new Error("workflow save failed");
        }
        return response.json();
    }

    document.querySelectorAll("[data-workflow-status-select]").forEach((select) => {
        select.addEventListener("change", async () => {
            const candidateId = select.getAttribute("data-candidate-id");
            if (!candidateId) {
                return;
            }
            select.disabled = true;
            try {
                const result = await saveWorkflow(candidateId, { status: select.value });
                if (result && result.workflow) {
                    syncWorkflowBadges(candidateId, result.workflow);
                }
            } catch (_error) {
                select.classList.add("is-error");
            } finally {
                select.disabled = false;
            }
        });
    });

    document.querySelectorAll("[data-workflow-notes-save]").forEach((button) => {
        button.addEventListener("click", async () => {
            const candidateId = button.getAttribute("data-candidate-id");
            const panel = button.closest("[data-component='NotePanel']");
            const input = panel ? panel.querySelector("[data-workflow-notes]") : null;
            const statusEl = panel ? panel.querySelector("[data-workflow-save-status]") : null;
            if (!candidateId || !input) {
                return;
            }
            button.disabled = true;
            if (statusEl) {
                statusEl.textContent = "保存中...";
            }
            try {
                await saveWorkflow(candidateId, { notes: input.value });
                if (statusEl) {
                    statusEl.textContent = "保存しました";
                }
            } catch (_error) {
                if (statusEl) {
                    statusEl.textContent = "保存に失敗しました";
                }
            } finally {
                button.disabled = false;
            }
        });
    });

    initContinuousProfitAnalysis();
});

function initContinuousProfitAnalysis() {
    const continuousBtn = document.querySelector("[data-profit-continuous]");
    const panel = document.querySelector("[data-continuous-profit-panel]");
    if (!continuousBtn || !panel) {
        return;
    }
    const batchId = continuousBtn.getAttribute("data-batch-id") || panel.getAttribute("data-batch-id");
    if (!batchId) {
        return;
    }
    const onceBtn = document.querySelector("[data-profit-once]");
    const stopBtn = panel.querySelector("[data-profit-stop]");
    const resumeBtn = panel.querySelector("[data-profit-resume]");
    const titleEl = panel.querySelector("[data-continuous-title]");
    const progressEl = panel.querySelector("[data-continuous-progress]");
    const remainingEl = panel.querySelector("[data-continuous-remaining]");
    const detailEl = panel.querySelector("[data-continuous-detail]");
    const costSelect = document.getElementById("profit-cost-profile");
    const cacheInput = document.getElementById("profit-use-cache");

    let pollTimer = null;
    let starting = false;
    let lastAnalyzed = null;

    function setBusy(isBusy) {
        if (onceBtn) {
            onceBtn.disabled = isBusy;
        }
        continuousBtn.disabled = isBusy;
    }

    function render(progress) {
        panel.hidden = false;
        const analyzed = progress.analyzed != null ? progress.analyzed : 0;
        const eligible = progress.eligible != null ? progress.eligible : 0;
        const remaining = progress.remaining != null ? progress.remaining : 0;
        const status = progress.status || "idle";

        if (titleEl) {
            if (status === "error") {
                titleEl.textContent = "分析中にエラーが発生しました。";
            } else if (status === "complete") {
                titleEl.textContent = progress.user_message || "すべて分析済みです。";
            } else if (status === "stopped") {
                titleEl.textContent = "連続分析を停止しました。";
            } else if (status === "busy") {
                titleEl.textContent = "現在このワークスペースでは分析が実行中です。";
            } else if (status === "stopping") {
                titleEl.textContent = "停止中（現在の20件完了待ち）...";
            } else {
                titleEl.textContent = "連続分析中...";
            }
        }
        if (progressEl) {
            if (status === "error") {
                progressEl.textContent =
                    "最後に完了した件数:\n" +
                    (progress.last_completed_count != null ? progress.last_completed_count : analyzed) +
                    "件";
            } else {
                progressEl.textContent = analyzed + " / " + eligible + " 完了";
            }
        }
        if (remainingEl) {
            remainingEl.textContent = remaining > 0 ? "残り" + remaining + "件" : "残り0件";
        }
        if (detailEl) {
            detailEl.textContent = progress.detail_message || progress.status_message || "";
        }

        const active = status === "running" || status === "stopping";
        setBusy(active);
        if (stopBtn) {
            stopBtn.hidden = !active;
            continuousBtn.hidden = active;
            if (!active) {
                continuousBtn.textContent = remaining > 0 ? "連続分析" : "連続分析";
                continuousBtn.hidden = false;
            }
        }
        if (resumeBtn) {
            resumeBtn.hidden = !(status === "error" || status === "stopped") || remaining <= 0;
        }

        if (
            active &&
            lastAnalyzed !== null &&
            analyzed !== lastAnalyzed &&
            typeof analyzed === "number"
        ) {
            // Soft ranking refresh after each completed tranche.
            // Full reload only when finished to keep polling stable.
        }
        lastAnalyzed = analyzed;
        return status;
    }

    async function fetchStatus() {
        const response = await fetch(
            "/acquisition-workspace/" + encodeURIComponent(batchId) + "/continuous-profit/status",
            { headers: { Accept: "application/json" } }
        );
        if (!response.ok) {
            throw new Error("status " + response.status);
        }
        return response.json();
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    function startPolling() {
        stopPolling();
        pollTimer = setInterval(async () => {
            try {
                const progress = await fetchStatus();
                const status = render(progress);
                if (status === "complete" || status === "stopped" || status === "error") {
                    stopPolling();
                    setBusy(false);
                    continuousBtn.hidden = false;
                    if (status === "complete" || status === "stopped") {
                        window.setTimeout(() => {
                            const url = new URL(window.location.href);
                            url.searchParams.set("batch_id", batchId);
                            if (status === "complete") {
                                url.searchParams.set("profit_done", "1");
                            }
                            window.location.href = url.toString();
                        }, 600);
                    }
                }
            } catch (_err) {
                // Keep polling; transient network blips should not crash the UI.
            }
        }, 1500);
    }

    async function startContinuous() {
        if (starting) {
            return;
        }
        starting = true;
        setBusy(true);
        continuousBtn.hidden = true;
        if (stopBtn) {
            stopBtn.hidden = false;
        }
        panel.hidden = false;
        if (titleEl) {
            titleEl.textContent = "連続分析中...";
        }
        try {
            const payload = {
                cost_profile: costSelect ? costSelect.value : "standard",
                use_cache: cacheInput ? cacheInput.checked : true,
            };
            const response = await fetch(
                "/acquisition-workspace/" + encodeURIComponent(batchId) + "/continuous-profit/start",
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        Accept: "application/json",
                    },
                    body: JSON.stringify(payload),
                }
            );
            const progress = await response.json();
            render(progress);
            if (progress.status === "busy") {
                starting = false;
                setBusy(false);
                continuousBtn.hidden = false;
                return;
            }
            if (progress.status === "complete") {
                starting = false;
                setBusy(false);
                continuousBtn.hidden = false;
                return;
            }
            startPolling();
        } catch (_err) {
            if (titleEl) {
                titleEl.textContent = "分析中にエラーが発生しました。";
            }
            setBusy(false);
            continuousBtn.hidden = false;
            if (stopBtn) {
                stopBtn.hidden = true;
            }
        } finally {
            starting = false;
        }
    }

    continuousBtn.addEventListener("click", (event) => {
        event.preventDefault();
        startContinuous();
    });

    if (stopBtn) {
        stopBtn.addEventListener("click", async () => {
            stopBtn.disabled = true;
            try {
                const response = await fetch(
                    "/acquisition-workspace/" + encodeURIComponent(batchId) + "/continuous-profit/stop",
                    { method: "POST", headers: { Accept: "application/json" } }
                );
                const progress = await response.json();
                render(progress);
            } catch (_err) {
                // ignore
            } finally {
                stopBtn.disabled = false;
            }
        });
    }

    if (resumeBtn) {
        resumeBtn.addEventListener("click", (event) => {
            event.preventDefault();
            startContinuous();
        });
    }

    // Restore panel if a run is already active (e.g. refreshed tab).
    fetchStatus()
        .then((progress) => {
            if (progress.status === "running" || progress.status === "stopping") {
                render(progress);
                startPolling();
            }
        })
        .catch(() => {});
}