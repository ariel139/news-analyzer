import { useData } from "../data";
import { fullDate } from "../format";
import type { Article } from "../types";
import { OutletBadge } from "./OutletBadge";

/** Outlet, time and topic tags above an article title (drawer and article page). */
export function ArticleMeta({ a }: { a: Article }) {
  const { meta } = useData();
  return (
    <div className="meta">
      <OutletBadge id={a.outlet} name={a.outlet_name} size={28} />
      <span className="outlet">{a.outlet_name}</span>
      <span className="dot" aria-hidden="true" />
      <time dateTime={a.published_at}>{fullDate(a.published_at, meta.timezone)}</time>
      {a.analysis && <><span className="tag">{a.analysis.topic_he}</span><span className="tag">{a.analysis.article_type_he}</span></>}
    </div>
  );
}
