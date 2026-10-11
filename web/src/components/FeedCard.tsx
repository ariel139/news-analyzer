import { Link, useLocation } from "react-router-dom";
import { useData } from "../data";
import { fullDate, relTime } from "../format";
import type { Article } from "../types";
import { OutletBadge } from "./OutletBadge";
import { Lean } from "./Scale";

/** One feed row. A plain click opens the article drawer over the feed; modified clicks open the full page. */
export function FeedCard({ a }: { a: Article }) {
  const { meta } = useData();
  const location = useLocation();
  const an = a.analysis;
  const ov = an?.axes.find((x) => x.key === "overall");
  return (
    <Link className="card" to={`/article/${a.id}`} state={{ background: location }}>
      <OutletBadge id={a.outlet} name={a.outlet_name} />
      <span className="card-body">
        <span className="meta">
          <span className="outlet">{a.outlet_name}</span>
          <span className="dot" aria-hidden="true" />
          <time dateTime={a.published_at} title={fullDate(a.published_at, meta.timezone)}>
            {relTime(a.published_at, meta.timezone)}
          </time>
          {an && <><span className="tag">{an.topic_he}</span><span className="tag tag-type">{an.article_type_he}</span></>}
        </span>
        <span className="card-title">{a.title}</span>
        {ov?.applicable ? (
          <Lean ov={ov} />
        ) : an ? (
          <span className="tag muted">{meta.leanings.na}</span>
        ) : a.status === "paywalled" ? (
          <span className="tag muted">בתשלום</span>
        ) : (
          <span className="tag muted">{a.status_he}</span>
        )}
      </span>
    </Link>
  );
}
