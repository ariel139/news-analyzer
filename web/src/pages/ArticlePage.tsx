import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { ArticleMeta } from "../components/ArticleMeta";
import { Icon } from "../components/Icon";
import { Panel } from "../components/Panel";
import { Shell } from "../components/Shell";
import { useFetch } from "../hooks";

/** The full analysis page, used for direct links and shared URLs. */
export function ArticlePage() {
  const { id = "" } = useParams();
  const { data: a, error, loading } = useFetch((signal) => api.article(id, signal), id);

  return (
    <Shell title={a?.title}>
      <div className="narrow">
        <nav className="crumbs" aria-label="פירורי לחם">
          <Link to="/">עדכונים</Link> <span aria-hidden="true">/</span> <span>{a?.outlet_name ?? "…"}</span>
        </nav>
        {loading && <div className="skeleton" aria-hidden="true"><span /><span /><span /><span /></div>}
        {error && (
          <p className="empty" role="alert">
            <strong>{error instanceof ApiError && error.status === 404 ? "הכתבה לא נמצאה" : "לא ניתן לטעון את הכתבה"}</strong>
            <Link to="/">חזרה לעדכונים</Link>
          </p>
        )}
        {a && (
          <>
            <article className="article-page">
              <header className="article-head">
                <ArticleMeta a={a} />
                <h1>{a.title}</h1>
              </header>
              <Panel a={a} />
            </article>
            <p className="disclaimer">
              <Icon name="info" />
              <span>הדירוג נוצר אוטומטית על ידי מודל בינה מלאכותית, הוא סובייקטיבי ועלול לטעות.</span>
            </p>
          </>
        )}
      </div>
    </Shell>
  );
}
