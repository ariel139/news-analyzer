// Page behaviours: filter shortcuts (topic rail, outlet pills, chips), filter popover/sheet,
// the article drawer, copy-link buttons, "/" to search, back-to-top.
(function () {
  var form = document.getElementById("filters");
  var phone = window.matchMedia("(max-width: 767px)");

  function syncShortcuts(name, value) {
    document.querySelectorAll('[data-filter="' + name + '"]').forEach(function (b) {
      var on = b.dataset.value === value;
      b.classList.toggle("active", on);
      if (b.tagName === "BUTTON") b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  // Query string for the address bar: only filters that are set.
  function feedQuery() {
    var p = new URLSearchParams();
    new FormData(form).forEach(function (v, k) {
      if (v && !(k === "analyzed" && v === "0")) p.append(k, v);
    });
    var s = p.toString();
    return s ? "/?" + s : "/";
  }

  function reloadFeed() {
    form.dispatchEvent(new Event("change", { bubbles: true }));
  }

  // ---- filter popover (desktop) / bottom sheet (phone)
  var sheet = document.getElementById("filter-sheet");
  var sheetBackdrop = document.querySelector(".sheet-backdrop");

  function setSheet(open) {
    if (!sheet) return;
    sheet.classList.toggle("open", open);
    if (sheetBackdrop) sheetBackdrop.hidden = !open;
    document.body.classList.toggle("sheet-open", open && phone.matches);
    document.querySelectorAll('[aria-controls="filter-sheet"]').forEach(function (b) {
      b.setAttribute("aria-expanded", open ? "true" : "false");
    });
    if (open) { var first = sheet.querySelector("select"); if (first) first.focus({ preventScroll: true }); }
  }

  function updateFilterCount() {
    if (!sheet) return;
    var n = 0;
    sheet.querySelectorAll("select").forEach(function (s) { if (s.value) n++; });
    document.querySelectorAll("[data-filter-count]").forEach(function (el) {
      el.textContent = n;
      el.hidden = n === 0;
    });
  }

  // ---- article drawer
  var drawer = document.getElementById("drawer");
  var drawerBody = document.getElementById("drawer-body");
  var drawerBackdrop = document.querySelector(".drawer-backdrop");
  var opener = null;
  var feedUrl = location.pathname + location.search;
  var SKELETON = '<div class="skeleton" aria-hidden="true"><span></span><span></span><span></span><span></span></div>' +
                 '<p class="visually-hidden">טוען…</p>';

  function isOpen() { return drawer && drawer.classList.contains("open"); }

  function showDrawer() {
    drawerBody.innerHTML = SKELETON;
    drawerBody.scrollTop = 0;
    drawer.inert = false;
    drawer.classList.add("open");
    drawerBackdrop.hidden = false;
    document.body.classList.add("drawer-open");
    drawer.querySelector("[data-action='close-drawer']").focus({ preventScroll: true });
  }

  function hideDrawer() {
    if (!isOpen()) return;
    drawer.classList.remove("open");
    drawer.inert = true;
    drawerBackdrop.hidden = true;
    document.body.classList.remove("drawer-open");
    if (opener && document.contains(opener)) opener.focus({ preventScroll: true });
    opener = null;
  }

  // Closing from the UI goes through history so Back and ✕ end in the same state.
  function closeDrawer() {
    if (history.state && history.state.drawer) history.back();
    else { hideDrawer(); history.replaceState(null, "", feedUrl); }
  }

  if (drawer) {
    // Ctrl/Cmd/Shift-click opens the full page in a new tab: keep htmx from intercepting.
    document.addEventListener("click", function (e) {
      if ((e.ctrlKey || e.metaKey || e.shiftKey) && e.target.closest("[data-article]")) e.stopPropagation();
    }, true);

    window.addEventListener("popstate", function (e) {
      if (e.state && e.state.drawer) {
        showDrawer();
        htmx.ajax("GET", "/fragments/article/" + e.state.drawer, { target: "#drawer-body", swap: "innerHTML" });
      } else {
        hideDrawer();
      }
    });

    document.body.addEventListener("htmx:afterSwap", function (e) {
      if (e.detail.target !== drawerBody) return;
      var title = drawerBody.querySelector(".article-title");
      if (title) drawer.setAttribute("aria-label", title.textContent.trim());
    });
    document.body.addEventListener("htmx:responseError", function (e) {
      if (e.detail.target === drawerBody) drawerBody.innerHTML = '<p class="empty">לא ניתן לטעון את הניתוח. נסו שוב.</p>';
    });

    // Keep Tab inside the open drawer.
    drawer.addEventListener("keydown", function (e) {
      if (e.key !== "Tab") return;
      var f = drawer.querySelectorAll('a[href], button:not([disabled]), [tabindex="0"]');
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  }

  document.addEventListener("click", function (e) {
    var act = e.target.closest("[data-action]");
    if (act) {
      var a = act.dataset.action;
      if (a === "close-filters") setSheet(false);
      else if (a === "filters") setSheet(!(sheet && sheet.classList.contains("open")));
      else if (a === "close-drawer") closeDrawer();
      return;
    }

    // htmx loads the analysis into the drawer; this opens it and records the article URL.
    var art = drawer && e.target.closest("[data-article]");
    if (art) {
      var url = "/article/" + art.dataset.article;
      if (isOpen()) history.replaceState({ drawer: art.dataset.article }, "", url);
      else { feedUrl = location.pathname + location.search; history.pushState({ drawer: art.dataset.article }, "", url); }
      opener = art;
      showDrawer();
      return;
    }

    var copy = e.target.closest("[data-copy]");
    if (copy) {
      var link = location.origin + copy.getAttribute("data-copy");
      var label = copy.querySelector("[data-copy-label]") || copy;
      var done = function () {
        var old = label.textContent;
        label.textContent = "הקישור הועתק";
        setTimeout(function () { label.textContent = old; }, 1800);
      };
      if (navigator.clipboard) navigator.clipboard.writeText(link).then(done, function () { prompt("", link); });
      else prompt("", link);
      return;
    }

    if (!form) return;

    // Chips clear one filter.
    var chip = e.target.closest("[data-clear]");
    if (chip) {
      var name = chip.dataset.clear;
      var el = form.elements[name];
      if (!el) return;
      el.value = name === "analyzed" ? "0" : "";
      if (name === "topic" || name === "outlet") syncShortcuts(name, "");
      updateFilterCount();
      reloadFeed();
      return;
    }

    // Shortcuts set the matching form field and let htmx reload the feed. Off the front page
    // (no #filters form) the topic links simply navigate.
    var btn = e.target.closest("[data-filter]");
    if (!btn) return;
    var field = form.elements[btn.dataset.filter];
    if (!field) return;
    e.preventDefault();
    var value = btn.dataset.value;
    if (btn.tagName === "BUTTON" && value && field.value === value) value = "";  // second click clears
    field.value = value;
    syncShortcuts(btn.dataset.filter, value);
    updateFilterCount();
    reloadFeed();
    if (btn.closest(".topics")) window.scrollTo({ top: 0, behavior: "smooth" });
  });

  if (form) {
    form.addEventListener("change", function (e) {
      if (e.target.matches && e.target.matches("select")) syncShortcuts(e.target.name, e.target.value);
      updateFilterCount();
    });
    document.body.addEventListener("htmx:afterRequest", function (e) {
      if (e.detail.elt === form && e.detail.successful) {
        feedUrl = feedQuery();
        if (!isOpen()) history.replaceState(null, "", feedUrl);
      }
    });
    // Close the desktop popover when clicking elsewhere.
    document.addEventListener("pointerdown", function (e) {
      if (sheet && sheet.classList.contains("open") && !phone.matches && !e.target.closest(".filter-anchor")) setSheet(false);
    });
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      if (isOpen()) { closeDrawer(); return; }
      if (sheet && sheet.classList.contains("open")) { setSheet(false); return; }
    }
    if (e.key === "/" && !e.ctrlKey && !e.metaKey && !isOpen()) {
      var t = e.target;
      if (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
      var q = document.getElementById("q");
      if (q) { e.preventDefault(); q.focus(); q.select(); }
    }
  });

  var top = document.getElementById("to-top");
  if (top) {
    var onScroll = function () { top.hidden = window.scrollY < 900; };
    window.addEventListener("scroll", onScroll, { passive: true });
    top.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
    onScroll();
  }
})();
