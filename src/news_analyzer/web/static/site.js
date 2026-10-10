// Small page behaviours: copy-link buttons, sidebar shortcuts into the filter form, back-to-top.
(function () {
  document.addEventListener("click", function (e) {
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

    // Sidebar topic chips / outlet rows set the matching <select> and let htmx reload the feed.
    var btn = e.target.closest("[data-filter]");
    if (btn) {
      var form = document.getElementById("filters");
      var select = form && form.querySelector('select[name="' + btn.dataset.filter + '"]');
      if (!select) return;
      var value = select.value === btn.dataset.value ? "" : btn.dataset.value;
      select.value = value;
      document.querySelectorAll('[data-filter="' + btn.dataset.filter + '"]').forEach(function (b) {
        var on = b.dataset.value === value;
        b.classList.toggle("active", on);
        b.setAttribute("aria-pressed", on ? "true" : "false");
      });
      select.dispatchEvent(new Event("change", { bubbles: true }));
      form.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });

  // Keep sidebar highlights in sync when the user changes a <select> directly.
  document.addEventListener("change", function (e) {
    if (!e.target.matches || !e.target.matches("#filters select")) return;
    document.querySelectorAll('[data-filter="' + e.target.name + '"]').forEach(function (b) {
      var on = b.dataset.value === e.target.value;
      b.classList.toggle("active", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    });
  });

  var top = document.getElementById("to-top");
  if (top) {
    var onScroll = function () { top.hidden = window.scrollY < 900; };
    window.addEventListener("scroll", onScroll, { passive: true });
    top.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
    onScroll();
  }
})();
