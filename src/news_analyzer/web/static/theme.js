// Light by default; the toggle stores an explicit choice. The <head> snippet in base.html
// applies a stored choice before first paint so there's no flash.
(function () {
  var root = document.documentElement;
  var btn = document.getElementById("theme-toggle");
  if (!btn) return;

  function sync() {
    var dark = root.dataset.theme === "dark";
    btn.setAttribute("aria-pressed", dark ? "true" : "false");
    btn.setAttribute("aria-label", dark ? "מעבר למצב בהיר" : "מעבר למצב כהה");
    btn.title = btn.getAttribute("aria-label");
  }

  btn.addEventListener("click", function () {
    var next = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch (e) {}
    sync();
  });
  sync();
})();
