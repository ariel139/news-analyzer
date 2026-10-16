import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Chips } from "../components/Chips";
import { FeedCard } from "../components/FeedCard";
import { FilterBar } from "../components/FilterBar";
import { Icon } from "../components/Icon";
import { Shell } from "../components/Shell";
import { StatsRail } from "../components/StatsRail";
import { useData } from "../data";
import { parseFilters } from "../filters";
import { dayKey, dayLabel, relTime } from "../format";
import type { Article } from "../types";

interface FeedState {
  items: Article[];
  loading: boolean;
  more: boolean;
  error: boolean;
}

/** Articles for one filter query, appended page by page. A new query starts over. */
function useFeed(query: string, reloadKey: number) {
  const [state, setState] = useState<FeedState>({ items: [], loading: true, more: false, error: false });
  const pending = useRef<AbortController | null>(null);

  const fetchPage = useCallback((offset: number, append: boolean) => {
    pending.current?.abort();
    const ctl = (pending.current = new AbortController());
    const p = new URLSearchParams(query);
    if (offset) p.set("offset", String(offset));
    setState((s) => ({ ...(append ? s : { items: [], more: false }), loading: true, error: false }));
    api.articles(p.toString(), ctl.signal).then(
      (r) => setState((s) => ({ items: append ? [...s.items, ...r.items] : r.items, loading: false, more: r.items.length === r.page_size, error: false })),
      () => !ctl.signal.aborted && setState((s) => ({ ...s, loading: false, error: true })),
    );
  }, [query]);

  useEffect(() => {
    fetchPage(0, false);
    return () => pending.current?.abort();
  }, [fetchPage, reloadKey]);

  return { ...state, loadMore: () => fetchPage(state.items.length, true) };
}

export function FeedPage() {
  const { meta, overview, refreshOverview } = useData();
  const [params, setParams] = useSearchParams();
  const filters = parseFilters(params);
  const query = params.toString();
  const [reloadKey, setReloadKey] = useState(0);
  const feed = useFeed(query, reloadKey);
  const searchRef = useRef<HTMLInputElement>(null);
  const [showTop, setShowTop] = useState(false);

  const update = useCallback((mutate: (p: URLSearchParams) => void) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      mutate(next);
      return next;
    }, { replace: true });
  }, [setParams]);

  // "/" jumps to search, like on most news sites.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "/" || e.ctrlKey || e.metaKey) return;
      const t = e.target as HTMLElement;
      if (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
      e.preventDefault();
      searchRef.current?.focus();
      searchRef.current?.select();
    };
    const onScroll = () => setShowTop(window.scrollY >= 900);
    document.addEventListener("keydown", onKey);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  // The collection time the page was loaded with: anything collected after it is "new".
  const [loadedAt, setLoadedAt] = useState<string | null>(null);
  useEffect(() => {
    if (loadedAt === null && overview?.last_collected) setLoadedAt(overview.last_collected);
  }, [overview, loadedAt]);
  const newCount = useNewCount(loadedAt);

  function refresh() {
    setLoadedAt(null);
    setReloadKey((k) => k + 1);
    void refreshOverview();
  }

  let lastDay = "";
  return (
    <Shell end={<StatsRail />}>
      <div className="feed-head" id="latest">
        <div className="feed-title">
          <h1>עדכונים</h1>
          <span className="live">
            <span className="live-dot" aria-hidden="true" />
            {overview?.last_collected ? `עודכן ${relTime(overview.last_collected, meta.timezone)}` : "מתעדכן כל 15 דקות"}
          </span>
        </div>
        <FilterBar filters={filters} update={update} searchRef={searchRef} />
        <Chips filters={filters} update={update} />
      </div>

      <p className="disclaimer">
        <Icon name="info" />
        <span>הדירוגים נוצרים אוטומטית על ידי מודל בינה מלאכותית. הם סובייקטיביים, עלולים לטעות, ואינם קביעה עובדתית.</span>
      </p>

      <div className="new-banner" aria-live="polite">
        {newCount > 0 && (
          <button type="button" className="new-pill" onClick={refresh}>
            <span className="live-dot" aria-hidden="true" />
            {newCount === 1 ? "כתבה חדשה אחת" : `${newCount} כתבות חדשות`} · לחצו לרענון
          </button>
        )}
      </div>

      <ul id="feed" className={`feed${feed.loading ? " loading" : ""}`} aria-busy={feed.loading}>
        {feed.items.map((a) => {
          const day = dayKey(a.published_at, meta.timezone);
          const head = day !== lastDay;
          lastDay = day;
          return (
            <Fragment key={a.id}>
              {head && <li className="day-head"><h2>{dayLabel(day, meta.timezone)}</h2></li>}
              <li><FeedCard a={a} /></li>
            </Fragment>
          );
        })}
        {!feed.loading && !feed.error && feed.items.length === 0 && (
          <li className="empty"><strong>לא נמצאו כתבות</strong>נסו לשנות או לנקות את הסינון.</li>
        )}
        {feed.error && (
          <li className="empty" role="alert"><strong>לא ניתן לטעון את הכתבות</strong>נסו שוב בעוד רגע.</li>
        )}
        {feed.more && (
          <li className="more">
            <button type="button" className="btn ghost" disabled={feed.loading} onClick={feed.loadMore}>טען עוד כתבות</button>
          </li>
        )}
      </ul>

      {showTop && (
        <button type="button" className="to-top" aria-label="חזרה לראש העמוד" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
          <Icon name="chevUp" />
        </button>
      )}
    </Shell>
  );
}

/** How many articles were collected since the page loaded; polled every two minutes. */
function useNewCount(since: string | null): number {
  const [n, setN] = useState(0);
  useEffect(() => {
    setN(0);
    if (!since) return;
    const ctl = new AbortController();
    const poll = () => api.newCount(since, ctl.signal).then((r) => setN(r.n), () => {});
    const id = window.setInterval(poll, 120_000);
    return () => {
      ctl.abort();
      window.clearInterval(id);
    };
  }, [since]);
  return n;
}
