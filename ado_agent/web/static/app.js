(() => {
  const state = {
    category: "",
    jurisdiction: "",
    source_id: "",
    search: "",
    only_new: false,
    only_unread: false,
    only_read: false,
    only_bills: false,
    only_bookmarked: false,
    only_effective_changes: false,
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
    btnLogout: document.getElementById("btn-logout"),
    btnUsers: document.getElementById("btn-users"),
    progressBanner: document.getElementById("progress-banner"),
    progressText: document.getElementById("progress-text"),
    progressBar: document.getElementById("progress-bar"),
    kpiTotal: document.getElementById("kpi-total"),
    kpiJurisdiction: document.getElementById("kpi-jurisdiction"),
    kpiNew: document.getElementById("kpi-new"),
    kpiUnread: document.getElementById("kpi-unread"),
    kpiBills: document.getElementById("kpi-bills"),
    kpiEffectiveSub: document.getElementById("kpi-effective-sub"),
    kpiBookmarked: document.getElementById("kpi-bookmarked"),
    kpiLastRun: document.getElementById("kpi-lastrun"),
    sourcePills: document.getElementById("source-status-pills"),
    filterSearch: document.getElementById("filter-search"),
    filterJurisdiction: document.getElementById("filter-jurisdiction"),
    filterSource: document.getElementById("filter-source"),
    filterSort: document.getElementById("filter-sort"),
    categoryChips: document.getElementById("category-chips"),
    filterOnlyNew: document.getElementById("filter-only-new"),
    filterOnlyEffective: document.getElementById("filter-only-effective"),
    effCountBadge: document.getElementById("eff-count-badge"),
    filterOnlyUnread: document.getElementById("filter-only-unread"),
    filterOnlyRead: document.getElementById("filter-only-read"),
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
    chkRescanAfterKw: document.getElementById("chk-rescan-after-kw"),
    autoScanSelect: document.getElementById("auto-scan-select"),
    btnSaveSettings: document.getElementById("btn-save-settings"),
    modalUsers: document.getElementById("modal-users"),
    usersManagerList: document.getElementById("users-manager-list"),
    formAddUser: document.getElementById("form-add-user"),
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

  function buildAccentTolerantPattern(kw, allowSeparators = false) {
    const map = {
      a: "[aá]",
      á: "[aá]",
      e: "[eé]",
      é: "[eé]",
      i: "[ií]",
      í: "[ií]",
      o: "[oóöő]",
      ó: "[oóöő]",
      ö: "[oóöő]",
      ő: "[oóöő]",
      u: "[uúüű]",
      ú: "[uúüű]",
      ü: "[uúüű]",
      ű: "[uúüű]",
    };
    const chars = [...kw].map((ch) => {
      const low = ch.toLowerCase();
      if (kw.length >= 2 && map[low]) return map[low];
      return ch.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    });
    if (allowSeparators && chars.length >= 5 && chars.length <= 28) {
      return chars.join("[-\\s]?");
    }
    return chars.join("");
  }

  function highlightText(rawText, keywords) {
    const text = String(rawText || "");
    const searchTokens = state.search
      ? state.search
          .split(/\s+/)
          .map((t) => t.trim())
          .filter((t) => t.length >= 2)
      : [];
    const allTerms = [...(keywords || []), ...searchTokens];
    if (!text || !allTerms.length) return escapeHtml(text);
    const seen = new Set();
    const sorted = [];
    for (const k of allTerms) {
      if (!k || k.length < 2) continue;
      const low = k.toLowerCase();
      if (seen.has(low)) continue;
      seen.add(low);
      sorted.push(k);
    }
    sorted.sort((a, b) => b.length - a.length);
    const limited = sorted.slice(0, 14);
    if (!limited.length) return escapeHtml(text);
    try {
      const searchSet = new Set(searchTokens.map((t) => t.toLowerCase()));
      const patterns = limited.map((k) =>
        buildAccentTolerantPattern(k, searchSet.has(k.toLowerCase()))
      );
      const combined = new RegExp(`(${patterns.join("|")})`, "giu");
      let out = "";
      let lastIdx = 0;
      for (const m of text.matchAll(combined)) {
        const idx = m.index ?? 0;
        if (idx > lastIdx) out += escapeHtml(text.slice(lastIdx, idx));
        out += `<mark>${escapeHtml(m[0])}</mark>`;
        lastIdx = idx + m[0].length;
      }
      if (lastIdx < text.length) out += escapeHtml(text.slice(lastIdx));
      return out || escapeHtml(text);
    } catch (_) {
      return escapeHtml(text);
    }
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
    if (state.only_unread) params.set("only_unread", "1");
    if (state.only_read) params.set("only_read", "1");
    if (state.only_bills) params.set("only_bills", "1");
    if (state.only_bookmarked) params.set("only_bookmarked", "1");
    if (state.only_effective_changes) params.set("only_effective_changes", "1");
    if (state.sort_by) params.set("sort_by", state.sort_by);
    return params.toString();
  }

  async function fetchState() {
    const qs = buildFilterQuery();
    try {
      const res = await fetch(`/api/state?${qs}`);
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      if (!res.ok) {
        let errText = `HTTP ${res.status}`;
        try {
          const errJson = await res.json();
          if (errJson && errJson.error) errText = errJson.error;
        } catch (_) {}
        throw new Error(errText);
      }
      const data = await res.json();
      state.data = data;
      renderAll(data);
      if (data.scan_status && data.scan_status.running) {
        startScanPolling();
      }
    } catch (err) {
      els.itemsList.innerHTML = `
        <div class="empty-state">
          <h3>Hiba történt az adatok lekérésekor</h3>
          <p>${escapeHtml(err && err.message ? err.message : "Ismeretlen hiba a szerverrel való kommunikáció során.")}</p>
        </div>
      `;
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
    const effTotal = st.effective_changes_count || 0;
    const upCnt = st.upcoming_changes_count || 0;
    const infCnt = st.in_force_changes_count || 0;
    if (els.kpiEffectiveSub) {
      els.kpiEffectiveSub.textContent = `Jövőbeli változás: ${upCnt} • Hatályba lépett: ${infCnt}`;
    }
    if (els.effCountBadge) {
      els.effCountBadge.textContent = effTotal;
    }
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
      let emptyDetail =
        "Kattints a fenti <strong>„Ellenőrzés most”</strong> gombra a magyar és EU-s oldalak lekérdezéséhez, vagy lazíts a szűrőkön.";
      if (state.category === "egyeni") {
        const kws = data.custom_keywords || [];
        if (!kws.length) {
          emptyDetail =
            "Még nincs megadva egyéni kulcsszó. Nyisd meg felül a <strong>„⚙ Kulcsszavak &amp; Ütemezés”</strong> ablakot a saját kulcsszavaid felvételéhez.";
        } else {
          emptyDetail = `Aktív egyéni kulcsszavak: <strong>${escapeHtml(kws.join(", "))}</strong>. A jelenlegi szűrők mellett még nincs egyező cikk — kattints az <strong>„Ellenőrzés most”</strong> gombra vagy lazíts a szűrőkön.`;
        }
      }
      els.itemsList.innerHTML = `
        <div class="empty-state">
          <h3>Nincs megjeleníthető adózási találat</h3>
          <p>${emptyDetail}</p>
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
      if (it.effective_status === "upcoming") {
        badges.push(
          `<span class="badge badge-eff-upcoming">⚠ Változás: ${escapeHtml(it.effective_date || "közelgő")}</span>`
        );
      } else if (it.effective_status === "in_force") {
        badges.push(
          `<span class="badge badge-eff-inforce">⚡ Hatályba lépett: ${escapeHtml(it.effective_date || "friss")}</span>`
        );
      } else if (it.effective_date) {
        badges.push(`<span class="badge badge-ref">Hatályos: ${escapeHtml(it.effective_date)}</span>`);
      }
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

      let effBannerHtml = "";
      if (it.effective_status === "upcoming") {
        effBannerHtml = `
          <div class="eff-banner eff-upcoming">
            <strong>⚠ Figyelmeztetés — közelgő hatálybalépés (${escapeHtml(it.effective_date)}):</strong>
            <span>Ez a jogszabály vagy módosítás a jelzett napon lép hatályba.</span>
          </div>
        `;
      } else if (it.effective_status === "in_force") {
        effBannerHtml = `
          <div class="eff-banner eff-inforce">
            <strong>⚡ Frissült — hatályba lépett (${escapeHtml(it.effective_date)}):</strong>
            <span>A módosított szabályozás hatályba lépett.</span>
          </div>
        `;
      }

      const changes = Array.isArray(it.change_summary) ? it.change_summary : [];
      const changesHtml = changes.length
        ? `
          <div class="change-details">
            <strong>Érintett változások / rendelkezések:</strong>
            <ul>${changes.map((c) => `<li>${highlightText(c, it.matched_keywords || [])}</li>`).join("")}</ul>
          </div>
        `
        : "";

      const comments = it.comments || [];
      const commentsHtml = comments
        .map(
          (c) => `
          <div class="comment-item">
            <div class="comment-header">
              <strong>${escapeHtml(c.author_name)}</strong>
              <span class="muted small">${escapeHtml(c.created_at)}</span>
              ${
                c.can_delete
                  ? `<button type="button" class="comment-del-btn" data-cid="${c.id}" title="Törlés">✕</button>`
                  : ""
              }
            </div>
            <div class="comment-body">${escapeHtml(c.body)}</div>
          </div>
        `
        )
        .join("");

      const legacyNoteHtml = it.notes
        ? `<div class="comment-item"><div class="comment-header"><strong>Korábbi jegyzet</strong></div><div class="comment-body">${escapeHtml(it.notes)}</div></div>`
        : "";

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
        ${effBannerHtml}
        ${changesHtml}
        ${it.summary ? `<p class="item-summary">${highlightedSummary}</p>` : ""}
        <div class="item-footer">
          <div>
            <strong>Kulcsszavak:</strong> ${escapeHtml((it.matched_keywords || []).join(", "))}
          </div>
          <div class="item-actions">
            <button type="button" class="btn btn-ghost btn-sm btn-bookmark">${it.is_bookmarked ? "★ Kiemelt" : "☆ Kiemelés"}</button>
            <button type="button" class="btn btn-ghost btn-sm btn-read">${it.is_read ? "↩ Olvasatlanná" : "✓ Olvasott"}</button>
            <button type="button" class="btn btn-ghost btn-sm btn-comments-toggle">💬 Megjegyzések (${comments.length})</button>
          </div>
        </div>
        <div class="comments-section ${comments.length || it.notes ? "" : "hidden"}">
          <div class="comments-list">${legacyNoteHtml}${commentsHtml}</div>
          <form class="comment-form">
            <input type="text" class="comment-input" placeholder="Megjegyzés hozzáadása a csoporthoz..." required>
            <button type="submit" class="btn btn-secondary btn-sm">Küldés</button>
          </form>
        </div>
      `;

      card.querySelector(".btn-bookmark").addEventListener("click", async () => {
        await updateFlags(it.item_key, { is_bookmarked: !it.is_bookmarked });
      });
      card.querySelector(".btn-read").addEventListener("click", async () => {
        await updateFlags(it.item_key, { is_read: !it.is_read });
      });
      const commentsSection = card.querySelector(".comments-section");
      card.querySelector(".btn-comments-toggle").addEventListener("click", () => {
        commentsSection.classList.toggle("hidden");
      });
      card.querySelector(".comment-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const input = card.querySelector(".comment-input");
        const bodyText = input.value.trim();
        if (!bodyText) return;
        const res = await fetch(`/api/items/${encodeURIComponent(it.item_key)}/comments`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body: bodyText }),
        });
        if (res.status === 401) {
          window.location.href = "/login";
          return;
        }
        if (res.ok) {
          input.value = "";
          showToast("Megjegyzés hozzáadva.");
          await fetchState();
        } else {
          const err = await res.json();
          showToast(err.error || "Hiba a mentésnél.");
        }
      });
      card.querySelectorAll(".comment-del-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const cid = btn.getAttribute("data-cid");
          const res = await fetch(`/api/comments/${cid}`, { method: "DELETE" });
          if (res.ok) {
            showToast("Megjegyzés törölve.");
            await fetchState();
          } else {
            const err = await res.json();
            showToast(err.error || "Nem sikerült törölni.");
          }
        });
      });

      els.itemsList.appendChild(card);
    }
  }

  async function updateFlags(itemKey, payload) {
    const res = await fetch(`/api/items/${encodeURIComponent(itemKey)}/flags`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }
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
      if (res.status === 401) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
        window.location.href = "/login";
        return;
      }
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
    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }
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
  if (els.filterOnlyEffective) {
    els.filterOnlyEffective.addEventListener("change", () => {
      state.only_effective_changes = els.filterOnlyEffective.checked;
      fetchState();
    });
  }
  if (els.filterOnlyUnread) {
    els.filterOnlyUnread.addEventListener("change", () => {
      state.only_unread = els.filterOnlyUnread.checked;
      if (state.only_unread && els.filterOnlyRead) {
        els.filterOnlyRead.checked = false;
        state.only_read = false;
      }
      fetchState();
    });
  }
  if (els.filterOnlyRead) {
    els.filterOnlyRead.addEventListener("change", () => {
      state.only_read = els.filterOnlyRead.checked;
      if (state.only_read && els.filterOnlyUnread) {
        els.filterOnlyUnread.checked = false;
        state.only_unread = false;
      }
      fetchState();
    });
  }
  els.filterOnlyBills.addEventListener("change", () => {
    state.only_bills = els.filterOnlyBills.checked;
    fetchState();
  });
  els.filterOnlyBookmarked.addEventListener("change", () => {
    state.only_bookmarked = els.filterOnlyBookmarked.checked;
    fetchState();
  });
  els.btnMarkAllRead.addEventListener("click", async () => {
    const res = await fetch("/api/items/mark-all-read", { method: "POST" });
    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }
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

  function commitPendingKeywordInput() {
    const raw = (els.newKwInput.value || "").trim();
    if (!raw) return false;
    let added = false;
    for (const part of raw.split(/[,;]+/)) {
      const kw = part.trim().replace(/\s+/g, " ");
      if (!kw) continue;
      if (!state.draftKeywords.some((k) => k.toLowerCase() === kw.toLowerCase())) {
        state.draftKeywords.push(kw);
        added = true;
      }
    }
    els.newKwInput.value = "";
    if (added) renderDraftKeywords();
    return added;
  }

  els.btnAddKw.addEventListener("click", () => {
    commitPendingKeywordInput();
    els.newKwInput.focus();
  });

  els.newKwInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      commitPendingKeywordInput();
    }
  });

  els.btnSaveSettings.addEventListener("click", async () => {
    commitPendingKeywordInput();
    const prevKeywords = ((state.data && state.data.custom_keywords) || [])
      .map((k) => k.toLowerCase())
      .join("\u0001");
    const nextKeywords = state.draftKeywords.map((k) => k.toLowerCase()).join("\u0001");
    const keywordsChanged = prevKeywords !== nextKeywords;
    const shouldRescan = Boolean(
      keywordsChanged && els.chkRescanAfterKw && els.chkRescanAfterKw.checked
    );

    const res = await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        custom_keywords: state.draftKeywords,
        auto_scan_interval_minutes: Number(els.autoScanSelect.value || 0),
        rescan: shouldRescan,
      }),
    });
    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }
    if (res.ok) {
      const resData = await res.json();
      els.modalSettings.classList.add("hidden");
      await fetchState();
      if (resData.scan_started) {
        startScanPolling();
      }
      const reclass = resData.reclassified || {};
      if (state.draftKeywords.length) {
        const matched = reclass.custom_matched || 0;
        const suffix = resData.scan_started ? " Friss ellenőrzés is elindult a háttérben." : "";
        showToast(`Beállítások mentve — ${matched} tárolt találat egyezik.${suffix}`);
      } else {
        showToast("Beállítások mentve.");
      }
    }
  });

  // Kijelentkezés & Csoportkezelés
  if (els.btnLogout) {
    els.btnLogout.addEventListener("click", async () => {
      await fetch("/api/auth/logout", { method: "POST" });
      window.location.href = "/login";
    });
  }

  async function renderUsersModal() {
    const res = await fetch("/api/users");
    if (!res.ok) return;
    const data = await res.json();
    els.usersManagerList.innerHTML = "";
    for (const u of data.users || []) {
      const row = document.createElement("div");
      row.className = "src-mgr-row";
      row.innerHTML = `
        <div>
          <strong>${escapeHtml(u.display_name)}</strong>
          <span class="muted small">(@${escapeHtml(u.username)})</span>
          ${u.is_admin ? `<span class="badge badge-eu">Admin</span>` : ""}
        </div>
        <button type="button" class="btn btn-ghost btn-sm btn-del-user">Törlés</button>
      `;
      row.querySelector(".btn-del-user").addEventListener("click", async () => {
        const delRes = await fetch(`/api/users/${u.id}`, { method: "DELETE" });
        if (delRes.ok) {
          showToast("Felhasználó törölve.");
          renderUsersModal();
        } else {
          const err = await delRes.json();
          showToast(err.error || "Nem törölhető.");
        }
      });
      els.usersManagerList.appendChild(row);
    }
  }

  if (els.btnUsers) {
    els.btnUsers.addEventListener("click", () => {
      renderUsersModal();
      els.modalUsers.classList.remove("hidden");
    });
  }

  if (els.formAddUser) {
    els.formAddUser.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        username: document.getElementById("new-user-username").value.trim(),
        display_name: document.getElementById("new-user-display").value.trim(),
        password: document.getElementById("new-user-password").value,
        is_admin: document.getElementById("new-user-admin").checked,
      };
      const res = await fetch("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        els.formAddUser.reset();
        showToast("Csoporttag létrehozva.");
        renderUsersModal();
      } else {
        const err = await res.json();
        showToast(err.error || "Hiba történt.");
      }
    });
  }

  // Kilépés (csak lokális asztali módban)
  if (els.btnShutdown) {
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
  }

  // Indulás
  fetchState();
})();
