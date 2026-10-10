// Small page behaviours: copy-link buttons, filter shortcuts (section bar, outlet row, sidebar), phone filter sheet, back-to-top.
(function () {
  function syncShortcuts(name, value) {
    document.querySelectorAll('[data-filter="' + name + '"]').forEach(function (b) {
      var on = b.dataset.value === value;
      b.classList.toggle("active", on);
      if (b.tagName === "BUTTON") b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  // ---- phone filter sheet
  var sheet = document.getElementById("filter-sheet");
  var backdrop = document.querySelector(".sheet-backdrop");

  function setSheet(open) {
    if (!sheet) return;
    sheet.classList.toggle("open", open);
    if (backdrop) backdrop.hidden = !open;
    document.body.classList.toggle("sheet-open", open);
    document.querySelectorAll('[aria-controls="filter-sheet"]').forEach(function (b) {
      b.setAttribute("aria-expanded", open ? "true" : "false");
    });
    if (open) { var first = sheet.querySelector("select"); if (first) first.focus({ preventScroll: true }); }
  }

  function updateFilterCount() {
    if (!sheet) return;
    var n = 0;
    sheet.querySelectorAll("select").forEach(function (s) { if (s.value) n++; });
    sheet.querySelectorAll('input[type="checkbox"]').forEach(function (c) { if (c.checked) n++; });
    document.querySelectorAll("[data-filter-count]").forEach(function (el) {
      el.textContent = n;
      el.hidden = n === 0;
    });
  }

  document.addEventListener("click", function (e) {
    var act = e.target.closest("[data-action]");
    if (act) {
      var a = act.dataset.action;
      if (a === "close-filters") { setSheet(false); return; }
      if (a === "filters") setSheet(true);
      return;
    }

    var copy = e.target.closest("[data-copy]");
    if (copy) {
      var url = location.origin + copy.getAttribute("data-copy");
      var label = copy.querySelector("[data-copy-label]") || copy;
      var done = function () {
        var old = label.textContent;
        label.textContent = "הקישור הועתק";
        setTimeout(function () { label.textContent = old; }, 1800);
      };
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, function () { prompt("", url); });
      else prompt("", url);
      return;
    }

    // Shortcuts set the matching form field and let htmx reload the feed. Off the front page
    // (no #filters form) the section-bar links simply navigate.
    var btn = e.target.closest("[data-filter]");
    var form = document.getElementById("filters");
    if (!btn || !form) return;
    var field = form.elements[btn.dataset.filter];
    if (!field) return;
    e.preventDefault();
    var value = btn.dataset.value;
    if (btn.tagName === "BUTTON" && value && field.value === value) value = "";  // second click clears
    field.value = value;
    syncShortcuts(btn.dataset.filter, value);
    field.dispatchEvent(new Event("change", { bubbles: true }));
    document.getElementById("latest").scrollIntoView({ behavior: "smooth", block: "start" });
  });

  document.addEventListener("change", function (e) {
    if (e.target.matches && e.target.matches("#filters select")) syncShortcuts(e.target.name, e.target.value);
    updateFilterCount();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && sheet && sheet.classList.contains("open")) setSheet(false);
  });

  var top = document.getElementById("to-top");
  if (top) {
    var onScroll = function () { top.hidden = window.scrollY < 900; };
    window.addEventListener("scroll", onScroll, { passive: true });
    top.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
    onScroll();
  }
})();
