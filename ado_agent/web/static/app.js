(() => {
  const state = {
    category: "",
    jurisdiction: "",
    source_id: "",
    search: "",
    only_new: false,
    only_bills: false,
    only_bookmarked: false,
    sort_by: "relevance",
    data: null,
    pollTimer: null,
    draftKeywords: [],
  };

  const els = {
    btnScan: document.getElementById("btn-scan"),
    btnExportToggle: document.getElementById("btn-export-toggle"),
    exportMenu: document.getElementById("export-menu"),
    btnSources: document.getElementById("btn-sources"),
    btnSettings: document.getElementById("btn-settings"),
    btnShutdown: document.getElementById("btn-shutdown"),
    progressBanner: document.getElementById("progress-banner"),
    progressText: document.getElementById("progress-text"),
    progressBar: document.getElementById("progress-bar"),
    kpiTotal: document.getElementById("kpi-total"),
    kpiJurisdiction: document.getElementById("kpi-jurisdiction"),
    kpiNew: document.getElementById("kpi-new"),
    kpiUnread: document.getElementById("kpi-unread"),
    kpiBills: document.getElementById("kpi-bills"),
    kpiBookmarked: document.getElementById("kpi-bookmarked"),
    kpiLastRun: document.getElementById("kpi-lastrun"),
    sourcePills: document.getElementById("source-status-pills"),
    filterSearch: document.getElementById("filter-search"),
    filterJurisdiction: document.getElementById("filter-jurisdiction"),
    filterSource: document.getElementById("filter-source"),
    filterSort: document.getElementById("filter-sort"),
    categoryChips: document.getElementById("category-chips"),
    filterOnlyNew: document.getElementById("filter-only-new"),
    filterOnlyBills: document.getElementById("filter-only-bills"),
    filterOnlyBookmarked: document.getElementById("filter-only-bookmarked"),
    btnMarkAllRead: document.getElementById("btn-mark-all-read"),
    resultsCount: document.getElementById("results-count"),
    itemsList: document.getElementById("items-list"),
    modalSources: document.getElementById("modal-sources"),
    sourcesManagerList: document.getElementById("sources-manager-list"),
    formAddSource: document.getElementById("form-add-source"),
    modalSettings: document.getElementById("modal-settings"),
    builtinCatsList: document.getElementById("builtin-categories-list"),
    newKwInput: document.getElementById("new-kw-input"),
    btnAddKw: document.getElementById("btn-add-kw"),
    customKwTags: document.getElementById("custom-kw-tags"),
    autoScanSelect: document.getElementById("auto-scan-select"),
    btnSaveSettings: document.getElementById("btn-save-settings"),
    toast: document.getElementById("toast"),
  };

  function escapeHtml(str) {
    return String(str || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function highlightText(rawText, keywords) {
    let safe = escapeHtml(rawText || "");
    if (!keywords || !keywords.length) return safe;
    const sorted = [...keywords]
      .filter((k) => k && k.length >= 2)
      .sort((a, b) => b.length - a.length)
      .slice(0, 10);
    for (const kw of sorted) {
      const escapedKw = escapeHtml(kw).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      try {
        const re = new RegExp(`(${escapedKw})`, "gi");
        safe = safe.replace(re, "<mark>$1</mark>");
      } catch (_) {}
    }
    return safe;
  }

  function showToast(msg) {
    els.toast.textContent = msg;
    els.toast.classList.remove("hidden");
    setTimeout(() => els.toast.classList.add("hidden"), 3200);
  }

  function buildFilterQuery() {
    const params = new URLSearchParams();
    if (state.jurisdiction) params.set("jurisdiction", state.jurisdiction);
    if (state.category) params.set("category", state.category);
    if (state.source_id) params.set("source_id", state.source_id);
    if (state.search) params.set("search", state.search);
    if (state.only_new) params.set("only_new", "1");
    if (state.only_bills) params.set("only_bills", "1");
    if (state.only_bookmarked) params.set("only_bookmarked", "1");
    if (state.sort_by) params.set("sort_by", state.sort_by);
    return params.toString();
  }

  async function fetchState() {
    const qs = buildFilterQuery();
    const res = await fetch(`/api/state?${qs}`);
    const data = await res.json();
    state.data = data;
    renderAll(data);
    if (data.scan_status && data.scan_status.running) {
      startScanPolling();
    }
  }

  function renderAll(data) {
    renderKpis(data);
    renderSourcePills(data);
    renderSourceFilter(data);
    renderCategoryChips(data);
    renderItems(data);
    renderScanBanner(data.scan_status);
  }

  function renderKpis(data) {
    const st = data.stats || {};
    els.kpiTotal.textContent = st.total ?? 0;
    const byJ = st.by_jurisdiction || {};
    els.kpiJurisdiction.textContent = `HU: ${byJ.HU || 0} • EU: ${byJ.EU || 0}`;
    els.kpiNew.textContent = (st.new_count || 0) + (st.updated_count || 0);
    els.kpiUnread.textContent = `Olvasatlan összesen: ${st.unread_count || 0}`;
    els.kpiBills.textContent = st.bills_count || 0;
    els.kpiBookmarked.textContent = st.bookmarked_count || 0;
    if (data.latest_run) {
      els.kpiLastRun.textContent = `Utolsó futás: ${data.latest_run.finished_at}`;
    } else {
      els.kpiLastRun.textContent = "Még nem futott ellenőrzés — kattints az Ellenőrzés most gombra!";
    }
  }

  function renderSourcePills(data) {
    const runMap = {};
    if (data.latest_run && Array.isArray(data.latest_run.source_results)) {
      for (const sr of data.latest_run.source_results) {
        runMap[sr.source_id] = sr;
      }
    }
    const counts = (data.stats && data.stats.by_source) || {};
    els.sourcePills.innerHTML = "";
    for (const src of data.sources || []) {
      const sr = runMap[src.id];
      const dotClass = !src.enabled ? "disabled" : sr ? sr.status : "";
      const pill = document.createElement("button");
      pill.type = "button";
      pill.className = "source-pill";
      pill.title = sr ? sr.message : src.description || src.url;
      const countText = counts[src.id] ? ` (${counts[src.id]})` : "";
      pill.innerHTML = `<span class="dot ${dotClass}"></span><span>${escapeHtml(src.name)}${countText}</span>`;
      pill.addEventListener("click", () => {
        state.source_id = state.source_id === src.id ? "" : src.id;
        els.filterSource.value = state.source_id;
        fetchState();
      });
      els.sourcePills.appendChild(pill);
    }
  }

  function renderSourceFilter(data) {
    const current = state.source_id;
    els.filterSource.innerHTML = `<option value="">Forrás: Összes</option>`;
    for (const src of data.sources || []) {
      const opt = document.createElement("option");
      opt.value = src.id;
      opt.textContent = src.name;
      els.filterSource.appendChild(opt);
    }
    els.filterSource.value = current;
  }

  function renderCategoryChips(data) {
    const byCat = (data.stats && data.stats.by_category) || {};
    const total = (data.stats && data.stats.total) || 0;
    const cats = [{ id: "", name: "Mind", count: total }].concat(
      (data.categories || []).map((c) => ({
        id: c.id,
        name: c.name,
        count: byCat[c.id] || 0,
      }))
    );

    els.categoryChips.innerHTML = "";
    for (const c of cats) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `cat-chip ${state.category === c.id ? "active" : ""}`;
      btn.innerHTML = `<span>${escapeHtml(c.name)}</span><span class="cat-count">${c.count}</span>`;
      btn.addEventListener("click", () => {
        state.category = c.id;
        fetchState();
      });
      els.categoryChips.appendChild(btn);
    }
  }

  function renderItems(data) {
    const items = data.items || [];
    els.resultsCount.textContent = `Találatok (${items.length})`;
    if (!items.length) {
      els.itemsList.innerHTML = `
        <div class="empty-state">
          <h3>Nincs megjeleníthető adózási találat</h3>
          <p>Kattints a fenti <strong>„Ellenőrzés most”</strong> gombra a magyar és EU-s oldalak lekérdezéséhez, vagy lazíts a szűrőkön.</p>
        </div>
      `;
      return;
    }

    els.itemsList.innerHTML = "";
    for (const it of items) {
      const card = document.createElement("article");
      card.className = "item-card";
      if (it.is_new) card.classList.add("is-new");
      else if (it.is_updated) card.classList.add("is-updated");
      if (it.is_read) card.classList.add("is-read");

      const badges = [];
      if (it.is_new) badges.push(`<span class="badge badge-new">ÚJ</span>`);
      else if (it.is_updated) badges.push(`<span class="badge badge-upd">FRISSÜLT</span>`);
      if (it.is_bill) badges.push(`<span class="badge badge-bill">Törvényjavaslat / Tervezet</span>`);
      badges.push(
        `<span class="badge ${it.jurisdiction === "EU" ? "badge-eu" : "badge-hu"}">${escapeHtml(it.jurisdiction)}</span>`
      );
      if (it.document_ref) badges.push(`<span class="badge badge-ref">${escapeHtml(it.document_ref)}</span>`);
      badges.push(`<span class="badge badge-score">Relevancia: ${it.relevance_score}/100</span>`);

      const catTags = (it.category_names || [])
        .map((c) => `<span class="item-cat-tag">${escapeHtml(c)}</span>`)
        .join("");

      const highlightedSummary = highlightText(it.summary || "", it.matched_keywords || []);
      const highlightedTitle = highlightText(it.title, it.matched_keywords || []);

      card.innerHTML = `
        <div class="item-meta">
          ${badges.join("")}
          <span class="muted">${escapeHtml(it.source_name)}</span>
          ${it.published_at ? `<span class="muted">• ${escapeHtml(it.published_at)}</span>` : ""}
        </div>
        <h3 class="item-title">
          <a href="${escapeHtml(it.url)}" target="_blank" rel="noopener noreferrer">${highlightedTitle}</a>
        </h3>
        <div class="item-cats">${catTags}</div>
        ${it.summary ? `<p class="item-summary">${highlightedSummary}</p>` : ""}
        <div class="item-footer">
          <div>
            <strong>Kulcsszavak:</strong> ${escapeHtml((it.matched_keywords || []).join(", "))}
          </div>
          <div class="item-actions">
            <button type="button" class="btn btn-ghost btn-sm btn-bookmark">${it.is_bookmarked ? "★ Kiemelt" : "☆ Kiemelés"}</button>
            <button type="button" class="btn btn-ghost btn-sm btn-read">${it.is_read ? "Olvasatlannak jelöl" : "✓ Olvasott"}</button>
            <button type="button" class="btn btn-ghost btn-sm btn-note-toggle">📝 Jegyzet</button>
          </div>
        </div>
        <div class="note-box ${it.notes ? "" : "hidden"}">
          <input type="text" class="note-input" value="${escapeHtml(it.notes || "")}" placeholder="Saját megjegyzés ehhez a jogszabályhoz...">
          <button type="button" class="btn btn-secondary btn-sm btn-note-save">Mentés</button>
        </div>
      `;

      card.querySelector(".btn-bookmark").addEventListener("click", async () => {
        await updateFlags(it.item_key, { is_bookmarked: !it.is_bookmarked });
      });
      card.querySelector(".btn-read").addEventListener("click", async () => {
        await updateFlags(it.item_key, { is_read: !it.is_read });
      });
      const noteBox = card.querySelector(".note-box");
      card.querySelector(".btn-note-toggle").addEventListener("click", () => {
        noteBox.classList.toggle("hidden");
      });
      card.querySelector(".btn-note-save").addEventListener("click", async () => {
        const val = card.querySelector(".note-input").value;
        await updateFlags(it.item_key, { notes: val });
        showToast("Jegyzet elmentve.");
      });

      els.itemsList.appendChild(card);
    }
  }

  async function updateFlags(itemKey, payload) {
    await fetch(`/api/items/${encodeURIComponent(itemKey)}/flags`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await fetchState();
  }

  function renderScanBanner(scanStatus) {
    if (!scanStatus) return;
    if (scanStatus.running) {
      els.btnScan.disabled = true;
      els.progressBanner.classList.remove("hidden");
      els.progressText.textContent = scanStatus.progress_message || "Ellenőrzés folyamatban...";
      const pct =
        scanStatus.progress_total > 0
          ? Math.max(8, Math.round((scanStatus.progress_done / scanStatus.progress_total) * 100))
          : 15;
      els.progressBar.style.width = `${pct}%`;
    } else {
      els.btnScan.disabled = false;
      els.progressBanner.classList.add("hidden");
    }
  }

  function startScanPolling() {
    if (state.pollTimer) return;
    state.pollTimer = setInterval(async () => {
      const res = await fetch("/api/scan/status");
      const data = await res.json();
      renderScanBanner(data.scan_status);
      if (!data.scan_status.running) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
        showToast(data.scan_status.progress_message || "Ellenőrzés kész.");
        await fetchState();
      }
    }, 900);
  }

  // Események
  els.btnScan.addEventListener("click", async () => {
    const res = await fetch("/api/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (res.ok) {
      const data = await res.json();
      renderScanBanner(data.scan_status);
      startScanPolling();
    } else {
      const err = await res.json();
      showToast(err.message || "Már fut egy ellenőrzés.");
    }
  });

  els.btnExportToggle.addEventListener("click", (e) => {
    e.stopPropagation();
    els.exportMenu.classList.toggle("hidden");
  });
  document.addEventListener("click", () => els.exportMenu.classList.add("hidden"));
  els.exportMenu.querySelectorAll("a[data-fmt]").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const fmt = a.getAttribute("data-fmt");
      const qs = buildFilterQuery();
      window.location.href = `/api/export/${fmt}?${qs}`;
      els.exportMenu.classList.add("hidden");
    });
  });

  // Szűrők
  let searchTimer = null;
  els.filterSearch.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.search = els.filterSearch.value.trim();
      fetchState();
    }, 240);
  });
  els.filterJurisdiction.addEventListener("change", () => {
    state.jurisdiction = els.filterJurisdiction.value;
    fetchState();
  });
  els.filterSource.addEventListener("change", () => {
    state.source_id = els.filterSource.value;
    fetchState();
  });
  els.filterSort.addEventListener("change", () => {
    state.sort_by = els.filterSort.value;
    fetchState();
  });
  els.filterOnlyNew.addEventListener("change", () => {
    state.only_new = els.filterOnlyNew.checked;
    fetchState();
  });
  els.filterOnlyBills.addEventListener("change", () => {
    state.only_bills = els.filterOnlyBills.checked;
    fetchState();
  });
  els.filterOnlyBookmarked.addEventListener("change", () => {
    state.only_bookmarked = els.filterOnlyBookmarked.checked;
    fetchState();
  });
  els.btnMarkAllRead.addEventListener("click", async () => {
    await fetch("/api/items/mark-all-read", { method: "POST" });
    showToast("Minden találat olvasottként jelölve.");
    await fetchState();
  });

  // Modálok
  document.querySelectorAll(".modal-close").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.getElementById(btn.getAttribute("data-close")).classList.add("hidden");
    });
  });

  els.btnSources.addEventListener("click", () => {
    renderSourcesModal();
    els.modalSources.classList.remove("hidden");
  });

  function renderSourcesModal() {
    const sources = (state.data && state.data.sources) || [];
    els.sourcesManagerList.innerHTML = "";
    for (const src of sources) {
      const row = document.createElement("div");
      row.className = "src-mgr-row";
      row.innerHTML = `
        <div>
          <strong>${escapeHtml(src.name)}</strong>
          <span class="badge ${src.jurisdiction === "EU" ? "badge-eu" : "badge-hu"}">${escapeHtml(src.jurisdiction)}</span>
          <div class="small muted">${escapeHtml(src.url)}</div>
          ${src.description ? `<div class="small muted">${escapeHtml(src.description)}</div>` : ""}
        </div>
        <div class="item-actions">
          <label class="toggle-chip">
            <input type="checkbox" ${src.enabled ? "checked" : ""}> Aktív
          </label>
          ${!src.is_builtin ? `<button type="button" class="btn btn-ghost btn-sm btn-del-src">Törlés</button>` : ""}
        </div>
      `;
      row.querySelector("input[type=checkbox]").addEventListener("change", async (e) => {
        await fetch(`/api/sources/${encodeURIComponent(src.id)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: e.target.checked }),
        });
        await fetchState();
        renderSourcesModal();
      });
      const delBtn = row.querySelector(".btn-del-src");
      if (delBtn) {
        delBtn.addEventListener("click", async () => {
          await fetch(`/api/sources/${encodeURIComponent(src.id)}`, { method: "DELETE" });
          await fetchState();
          renderSourcesModal();
          showToast("Forrás törölve.");
        });
      }
      els.sourcesManagerList.appendChild(row);
    }
  }

  els.formAddSource.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      name: document.getElementById("new-src-name").value.trim(),
      url: document.getElementById("new-src-url").value.trim(),
      jurisdiction: document.getElementById("new-src-jur").value,
      adapter: document.getElementById("new-src-adapter").value,
    };
    const res = await fetch("/api/sources", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      els.formAddSource.reset();
      await fetchState();
      renderSourcesModal();
      showToast("Új forrás hozzáadva.");
    } else {
      const err = await res.json();
      showToast(err.error || "Hiba történt.");
    }
  });

  // Kulcsszavak & Ütemezés modal
  els.btnSettings.addEventListener("click", () => {
    const data = state.data || {};
    state.draftKeywords = [...(data.custom_keywords || [])];
    els.autoScanSelect.value = String(data.auto_scan_interval_minutes || 0);
    renderBuiltinCats(data.categories || []);
    renderDraftKeywords();
    els.modalSettings.classList.remove("hidden");
  });

  function renderBuiltinCats(cats) {
    els.builtinCatsList.innerHTML = cats
      .filter((c) => c.id !== "egyeni")
      .map(
        (c) => `
        <div class="builtin-cat-box">
          <strong>${escapeHtml(c.name)}</strong>
          <div class="muted">${escapeHtml(c.description)}</div>
        </div>
      `
      )
      .join("");
  }

  function renderDraftKeywords() {
    if (!state.draftKeywords.length) {
      els.customKwTags.innerHTML = `<span class="small muted">Nincs megadva egyéni kulcsszó.</span>`;
      return;
    }
    els.customKwTags.innerHTML = "";
    state.draftKeywords.forEach((kw, idx) => {
      const tag = document.createElement("span");
      tag.className = "kw-tag";
      tag.innerHTML = `<span>${escapeHtml(kw)}</span><button type="button" title="Eltávolítás">✕</button>`;
      tag.querySelector("button").addEventListener("click", () => {
        state.draftKeywords.splice(idx, 1);
        renderDraftKeywords();
      });
      els.customKwTags.appendChild(tag);
    });
  }

  els.btnAddKw.addEventListener("click", () => {
    const kw = els.newKwInput.value.trim();
    if (!kw) return;
    if (!state.draftKeywords.some((k) => k.toLowerCase() === kw.toLowerCase())) {
      state.draftKeywords.push(kw);
      renderDraftKeywords();
    }
    els.newKwInput.value = "";
  });

  els.btnSaveSettings.addEventListener("click", async () => {
    const res = await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        custom_keywords: state.draftKeywords,
        auto_scan_interval_minutes: Number(els.autoScanSelect.value || 0),
      }),
    });
    if (res.ok) {
      els.modalSettings.classList.add("hidden");
      await fetchState();
      showToast("Beállítások mentve.");
    }
  });

  // Kilépés
  els.btnShutdown.addEventListener("click", async () => {
    if (!confirm("Biztosan leállítod az ADÓ Agent alkalmazást?")) return;
    try {
      await fetch("/api/shutdown", { method: "POST" });
    } catch (_) {}
    document.body.innerHTML = `
      <div style="max-width:560px;margin:80px auto;background:#fff;padding:30px;border-radius:14px;text-align:center;font-family:system-ui,sans-serif;border:1px solid #e2e8f0;">
        <h2>ADÓ Agent leállítva</h2>
        <p style="color:#475569;">Ez a böngészőfül most bezárható.</p>
      </div>
    `;
  });

  // Indulás
  fetchState();
})();
