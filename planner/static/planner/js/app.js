/* Richard & Denver — small bits of glue around htmx. */
(function () {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // ------------------------------------------------------------ CSRF / htmx
  function csrf() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }
  document.body.addEventListener("htmx:configRequest", (e) => {
    e.detail.headers["X-CSRFToken"] = csrf();
  });
  document.body.addEventListener("htmx:responseError", () => toast("Couldn't save that — check your connection and try again.", true));
  document.body.addEventListener("htmx:sendError", () => toast("You look to be offline — that change wasn't saved.", true));

  // ------------------------------------------------------------------ toast
  function toast(msg, isError) {
    const box = $("#toasts");
    if (!box || !msg) return;
    const t = document.createElement("div");
    t.className = "toast" + (isError ? " err" : "");
    t.textContent = msg;
    box.appendChild(t);
    setTimeout(() => t.remove(), 3600);
  }
  window.plannerToast = toast;

  // ---------------------------------------------------------- saved state
  let saveTimer;
  document.body.addEventListener("planner:saved", (e) => {
    const el = e.detail && e.detail.id ? document.getElementById(e.detail.id) : e.target;
    if (el) {
      el.classList.remove("is-saved");
      void el.offsetWidth;
      el.classList.add("is-saved");
    }
    const s = $("#save-state");
    if (s) {
      s.textContent = "Saved ✓";
      s.classList.add("show");
      clearTimeout(saveTimer);
      saveTimer = setTimeout(() => s.classList.remove("show"), 1800);
    }
    if (drawerOpen()) drawerDirty = true;
    // Some views regroup things when a value changes (e.g. the venue board).
    if (e.target.closest && e.target.closest("[data-refresh-on-save]") && e.target.matches("select")) refreshMain();
  });
  document.body.addEventListener("planner:error", (e) => toast(e.detail && e.detail.value, true));

  // Keep select colour-coding in step with what's chosen.
  document.body.addEventListener("change", (e) => {
    const el = e.target;
    if (el.matches("select.ctl-select")) el.dataset.value = el.value;
    if (el.matches(".done-check") && el.checked) leafBurst(el);
    if (el.matches(".burst-on-check") && el.checked) leafBurst(el);
  });

  // ------------------------------------------------- refresh main content
  let lastRefresh = Date.now();
  function refreshMain() {
    lastRefresh = Date.now();
    return htmx.ajax("GET", location.pathname + location.search, { target: "#main", select: "#main", swap: "outerHTML" });
  }
  window.plannerRefresh = refreshMain;

  document.body.addEventListener("planner:refresh", refreshMain);
  document.body.addEventListener("planner:created", (e) => {
    closeDrawer(false);
    toast((e.detail && e.detail.message) || "Added");
    refreshMain();
  });
  document.body.addEventListener("planner:deleted", (e) => {
    toast((e.detail && e.detail.message) || "Deleted");
    if (drawerOpen()) {
      closeDrawer(false);
      refreshMain();
    }
  });

  // Pick up the other person's changes when coming back to the tab.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") return;
    if (Date.now() - lastRefresh < 45000 || drawerOpen()) return;
    const a = document.activeElement;
    if (a && a.matches("input, textarea, select")) return;
    refreshMain();
  });

  // ----------------------------------------------------------------- drawer
  let drawerDirty = false;
  const drawerOpen = () => $("#drawer-root")?.classList.contains("open");

  function openDrawer() {
    const root = $("#drawer-root");
    root.classList.add("open");
    root.setAttribute("aria-hidden", "false");
    document.documentElement.style.overflow = "hidden";
    drawerDirty = false;
    setTimeout(() => {
      const first = $("#drawer-body [autofocus]") || $("#drawer-body input:not([type=hidden]), #drawer-body textarea");
      if (first && window.matchMedia("(min-width: 861px)").matches) first.focus();
    }, 250);
  }

  function closeDrawer(refreshIfDirty = true) {
    const root = $("#drawer-root");
    if (!root || !root.classList.contains("open")) return;
    root.classList.remove("open");
    root.setAttribute("aria-hidden", "true");
    document.documentElement.style.overflow = "";
    if (refreshIfDirty && drawerDirty) refreshMain();
    drawerDirty = false;
    const url = new URL(location.href);
    if (url.searchParams.has("open")) {
      url.searchParams.delete("open");
      history.replaceState(null, "", url);
    }
  }
  window.plannerCloseDrawer = closeDrawer;

  document.body.addEventListener("htmx:afterSwap", (e) => {
    // Only open for real content — a successful create replies with an empty body (and no swap).
    if (e.detail.target && e.detail.target.id === "drawer-body" && e.detail.xhr.responseText.trim()) openDrawer();
  });
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-close-drawer]")) closeDrawer();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (drawerOpen()) closeDrawer();
      closeMenus();
      $("#search-results") && ($("#search-results").innerHTML = "");
    }
  });

  function openFromUrl() {
    const p = new URLSearchParams(location.search).get("open");
    if (!p) return;
    const [slug, pk] = p.split(":");
    if (slug && /^\d+$/.test(pk)) htmx.ajax("GET", `/x/${slug}/${pk}/`, { target: "#drawer-body", swap: "innerHTML" });
  }

  // ------------------------------------------------------------ menus
  function closeMenus(except) {
    $$(".menu.open").forEach((m) => m !== except && m.classList.remove("open"));
    $$(".fab.open").forEach((f) => !except && f.classList.remove("open"));
    $("#more-sheet")?.classList.remove("open");
  }
  document.addEventListener("click", (e) => {
    const toggle = e.target.closest("[data-menu]");
    if (toggle) {
      const menu = document.getElementById(toggle.dataset.menu);
      const willOpen = !menu.classList.contains("open");
      closeMenus(menu);
      menu.classList.toggle("open", willOpen);
      toggle.classList.toggle("open", willOpen);
      e.stopPropagation();
      return;
    }
    if (e.target.closest("[data-more]")) {
      $("#more-sheet").classList.add("open");
      return;
    }
    if (e.target.closest("[data-close-more]")) {
      $("#more-sheet").classList.remove("open");
      return;
    }
    if (e.target.closest(".menu button, .menu a")) {
      closeMenus();
      return;
    }
    if (!e.target.closest(".menu")) closeMenus();
    if (!e.target.closest(".search")) {
      const r = $("#search-results");
      if (r) r.innerHTML = "";
    }
  });

  // --------------------------------------------------------- leaf confetti
  const LEAVES = ["🍃", "🌿", "🍂", "✨", "🌱", "💚"];
  function leafBurst(el) {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const r = el.getBoundingClientRect();
    for (let i = 0; i < 14; i++) {
      const s = document.createElement("span");
      s.className = "leaf";
      s.textContent = LEAVES[i % LEAVES.length];
      const angle = (Math.PI * 2 * i) / 14 + Math.random() * 0.4;
      const dist = 50 + Math.random() * 70;
      s.style.left = r.left + r.width / 2 - 9 + "px";
      s.style.top = r.top + r.height / 2 - 12 + "px";
      s.style.setProperty("--dx", Math.cos(angle) * dist + "px");
      s.style.setProperty("--dy", Math.sin(angle) * dist + 40 + "px");
      s.style.setProperty("--rot", (Math.random() * 360 - 180).toFixed(0) + "deg");
      s.style.fontSize = 13 + Math.random() * 10 + "px";
      document.body.appendChild(s);
      setTimeout(() => s.remove(), 1400);
    }
  }
  window.plannerLeafBurst = leafBurst;

  // ------------------------------------------- per-fragment initialisation
  htmx.onLoad((root) => {
    // Drag-and-drop venue lanes.
    if (window.Sortable) {
      $$("[data-lane]", root).forEach((lane) => {
        if (lane._sortable) return;
        lane._sortable = Sortable.create(lane, {
          group: "venues",
          animation: 180,
          delay: 180,
          delayOnTouchOnly: true,
          ghostClass: "sortable-ghost",
          chosenClass: "sortable-chosen",
          filter: "select, input, a.btn",
          preventOnFilter: false,
          onAdd: (evt) => {
            const card = evt.item;
            const status = evt.to.dataset.lane;
            htmx
              .ajax("POST", card.dataset.fieldUrl, { values: { _field: "status", status }, swap: "none", source: card })
              .then(() => {
                const sel = card.querySelector("select[name=status]");
                if (sel) {
                  sel.value = status;
                  sel.dataset.value = status;
                }
                if (status === "Booked") leafBurst(card);
                refreshMain();
              });
          },
        });
      });
    }

    // Image pickers: preview + paste a screenshot straight in.
    $$("[data-upload]", root).forEach((wrap) => {
      if (wrap._wired) return;
      wrap._wired = true;
      const input = wrap.querySelector("input[type=file]");
      const preview = wrap.parentElement.querySelector(".upload-preview");
      const show = () => {
        const f = input.files && input.files[0];
        if (!f || !preview) return;
        preview.src = URL.createObjectURL(f);
        preview.classList.add("show");
        const txt = wrap.querySelector(".txt");
        if (txt) txt.textContent = f.name || "Pasted image";
        if (wrap.dataset.autosubmit !== undefined) htmx.trigger(wrap.closest("form"), "submit");
      };
      input.addEventListener("change", show);
      const form = wrap.closest("form") || wrap.closest("[data-paste-target]");
      (form || document).addEventListener("paste", (e) => {
        const item = Array.from(e.clipboardData?.items || []).find((i) => i.type.startsWith("image/"));
        if (!item) return;
        const file = item.getAsFile();
        const dt = new DataTransfer();
        dt.items.add(new File([file], "pasted.png", { type: file.type }));
        input.files = dt.files;
        e.preventDefault();
        show();
      });
    });

    // Hearts pop.
    $$(".heart.pop", root).forEach((h) => setTimeout(() => h.classList.remove("pop"), 500));
  });

  document.addEventListener("DOMContentLoaded", openFromUrl);
  if (document.readyState !== "loading") openFromUrl();
})();
