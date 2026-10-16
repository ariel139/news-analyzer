import { useEffect, useRef, useState } from "react";
import { useData } from "../data";
import { activeFilterCount, type Filters } from "../filters";
import { Icon } from "./Icon";
import { OutletBadge } from "./OutletBadge";

interface Props {
  filters: Filters;
  /** Applies a change to the URL query (the single source of truth for filters). */
  update: (mutate: (p: URLSearchParams) => void) => void;
  searchRef: React.RefObject<HTMLInputElement | null>;
}

const phone = () => window.matchMedia("(max-width: 767px)").matches;

/** Search box plus the filter popover (desktop) / bottom sheet (phone). */
export function FilterBar({ filters, update, searchRef }: Props) {
  const { meta } = useData();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState(filters.q);
  const anchor = useRef<HTMLSpanElement>(null);
  const n = activeFilterCount(filters);

  // The URL is the source of truth: reflect changes made elsewhere (chips, "clear all").
  useEffect(() => setQ(filters.q), [filters.q]);

  // Debounced headline search.
  useEffect(() => {
    if (q === filters.q) return;
    const t = window.setTimeout(() => update((p) => (q.trim() ? p.set("q", q) : p.delete("q"))), 400);
    return () => window.clearTimeout(t);
  }, [q, filters.q, update]);

  useEffect(() => {
    if (!open) return;
    document.body.classList.toggle("sheet-open", phone());
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onPointer = (e: PointerEvent) => {
      if (!phone() && !anchor.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.body.classList.remove("sheet-open");
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  const toggleOutlet = (id: string, on: boolean) =>
    update((p) => {
      const rest = p.getAll("outlet").filter((o) => o !== id);
      p.delete("outlet");
      [...rest, ...(on ? [id] : [])].forEach((o) => p.append("outlet", o));
    });
  const setOrDelete = (key: string, value: string) => update((p) => (value ? p.set(key, value) : p.delete(key)));

  return (
    <form className="filters" role="search" onSubmit={(e) => e.preventDefault()}>
      <label className="search">
        <span className="visually-hidden">חיפוש בכותרות</span>
        <Icon name="search" />
        <input
          ref={searchRef} id="q" type="search" name="q" value={q} placeholder="חיפוש בכותרות…"
          autoComplete="off" maxLength={80} enterKeyHint="search" onChange={(e) => setQ(e.target.value)}
        />
        <kbd className="kbd" aria-hidden="true">/</kbd>
      </label>
      <span className="filter-anchor" ref={anchor}>
        <button type="button" className="filter-btn" aria-controls="filter-sheet" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
          <Icon name="filter" />
          <span>סינון</span>
          <span className="badge" hidden={n === 0}>{n}</span>
        </button>
        {open && <span className="sheet-backdrop" onClick={() => setOpen(false)} />}
        <div className={`filter-sheet${open ? " open" : ""}`} id="filter-sheet" role="group" aria-label="סינון כתבות">
          <div className="sheet-head">
            <h2>סינון כתבות</h2>
            <button type="button" className="icon-btn" aria-label="סגירה" onClick={() => setOpen(false)}>
              <Icon name="close" />
            </button>
          </div>
          <fieldset className="checks">
            <legend>מקורות <span>אפשר לבחור כמה</span></legend>
            {Object.entries(meta.outlets).map(([id, name]) => (
              <label key={id} className="check">
                <input type="checkbox" name="outlet" value={id} checked={filters.outlets.includes(id)} onChange={(e) => toggleOutlet(id, e.target.checked)} />
                <span><OutletBadge id={id} name={name} size={20} />{name}</span>
              </label>
            ))}
          </fieldset>
          <label className="select"><span>נטייה כללית</span>
            <select name="leaning" value={filters.leaning} onChange={(e) => setOrDelete("leaning", e.target.value)}>
              <option value="">כל הנטיות</option>
              {Object.entries(meta.leanings).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className="select"><span>סוג כתבה</span>
            <select name="type" value={filters.type} onChange={(e) => setOrDelete("type", e.target.value)}>
              <option value="">כל הסוגים</option>
              {Object.entries(meta.article_types).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label className="switch">
            <input type="checkbox" name="analyzed" role="switch" checked={filters.analyzed} onChange={(e) => setOrDelete("analyzed", e.target.checked ? "1" : "")} />
            <span className="switch-track" aria-hidden="true" />
            <span>רק כתבות שנותחו</span>
          </label>
          <p className="hint">סינון לפי נושא, נטייה או סוג מציג רק כתבות שכבר נותחו.</p>
          <div className="sheet-foot">
            <button type="button" className="btn ghost" onClick={() => { update((p) => [...p.keys()].forEach((k) => p.delete(k))); setOpen(false); }}>
              ניקוי הכול
            </button>
            <button type="button" className="btn" onClick={() => setOpen(false)}>הצגת התוצאות</button>
          </div>
        </div>
      </span>
    </form>
  );
}
