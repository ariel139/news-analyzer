import { useEffect, useState } from "react";
import { Icon } from "./Icon";

// Light by default; the toggle stores an explicit choice. The inline script in index.html applies
// a stored choice before first paint so there's no flash.
export function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.dataset.theme === "dark");

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", dark ? "#0c1110" : "#f1f4f3"); // phone browser chrome follows the theme
  }, [dark]);

  function toggle() {
    const next = !dark;
    setDark(next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      // private mode: the choice just doesn't persist
    }
  }

  const label = dark ? "מעבר למצב בהיר" : "מעבר למצב כהה";
  return (
    <button type="button" className="icon-btn theme-toggle" aria-label={label} title={label} aria-pressed={dark} onClick={toggle}>
      <Icon name="sun" className="sun" />
      <Icon name="moon" className="moon" />
    </button>
  );
}
