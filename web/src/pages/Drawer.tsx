import { useEffect, useRef } from "react";
import { Link, useNavigate, useParams, type Location } from "react-router-dom";
import { api } from "../api";
import { ArticleMeta } from "../components/ArticleMeta";
import { Icon } from "../components/Icon";
import { Panel } from "../components/Panel";
import { useFetch } from "../hooks";

/** The article analysis as a side sheet over the feed (full screen on a phone). */
export function Drawer({ background }: { background: Location }) {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { data: a, error, loading } = useFetch((signal) => api.article(id, signal), id);
  const ref = useRef<HTMLElement>(null);
  const closeBtn = useRef<HTMLButtonElement>(null);

  // Closing goes back through history so Back and ✕ end in the same state. After a reload there may be
  // no entry to go back to, so fall back to the feed the drawer was opened from.
  function close() {
    if ((window.history.state?.idx ?? 0) > 0) navigate(-1);
    else navigate({ pathname: background.pathname, search: background.search }, { replace: true });
  }
  const closeRef = useRef(close);
  closeRef.current = close;

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    document.body.classList.add("drawer-open");
    closeBtn.current?.focus({ preventScroll: true });
    return () => {
      document.body.classList.remove("drawer-open");
      if (opener && document.contains(opener)) opener.focus({ preventScroll: true });
    };
  }, []);

  useEffect(() => {
    const prev = document.title;
    if (a) document.title = `${a.title} · מנתח חדשות`;
    return () => void (document.title = prev);
  }, [a]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") return closeRef.current();
      if (e.key !== "Tab" || !ref.current) return;
      // Keep Tab inside the open drawer.
      const f = ref.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex="0"]');
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <div className="drawer-backdrop" onClick={close} />
      <aside ref={ref} className="drawer" role="dialog" aria-modal="true" aria-label={a?.title ?? "ניתוח הכתבה"}>
        <div className="drawer-bar">
          <button ref={closeBtn} type="button" className="icon-btn" aria-label="סגירה" onClick={close}>
            <Icon name="close" />
          </button>
        </div>
        <div className="drawer-body" aria-live="polite">
          {loading && (
            <>
              <div className="skeleton" aria-hidden="true"><span /><span /><span /><span /></div>
              <p className="visually-hidden">טוען…</p>
            </>
          )}
          {error && <p className="empty">לא ניתן לטעון את הניתוח. נסו שוב.</p>}
          {a && (
            <>
              <header className="article-head">
                <ArticleMeta a={a} />
                <h2 className="article-title" tabIndex={-1}>{a.title}</h2>
                <Link className="full-link" to={`/article/${a.id}`}>לעמוד הניתוח המלא</Link>
              </header>
              <Panel a={a} />
            </>
          )}
        </div>
      </aside>
    </>
  );
}
