import { Link, useLocation } from "react-router-dom";
import { useData } from "../data";
import { parseFilters } from "../filters";
import { BrandMark, Icon } from "./Icon";
import { ThemeToggle } from "./ThemeToggle";

/** Start rail: brand, main nav and topic shortcuts. On a phone it becomes the sticky top bar. */
export function Rail() {
  const { meta, overview } = useData();
  const { pathname, search } = useLocation();
  const onFeed = pathname === "/";
  const params = new URLSearchParams(onFeed ? search : "");
  const { topic, analyzed } = parseFilters(params);

  function topicTo(k: string) {
    const p = new URLSearchParams(params);
    if (k) p.set("topic", k);
    else p.delete("topic");
    const s = p.toString();
    return { pathname: "/", search: s ? `?${s}` : "" };
  }

  return (
    <header className="rail">
      <div className="rail-top">
        <Link className="brand" to="/" aria-label="מנתח חדשות, לעמוד הראשי">
          <span className="brand-mark" aria-hidden="true"><BrandMark /></span>
          <span className="brand-text">מנתח חדשות</span>
        </Link>
        <span className="rail-actions">
          <Link className="icon-btn" to="/methodology" aria-label="איך זה עובד" title="איך זה עובד" aria-current={pathname === "/methodology" ? "page" : undefined}>
            <Icon name="info" />
          </Link>
          <ThemeToggle />
        </span>
      </div>

      <nav className="nav" aria-label="ראשי">
        <Link className="nav-link" to="/" aria-current={onFeed && !analyzed ? "page" : undefined}>
          <Icon name="home" /><span>כל העדכונים</span>
        </Link>
        <Link className="nav-link" to="/?analyzed=1" aria-current={onFeed && analyzed ? "page" : undefined}>
          <Icon name="chart" /><span>כתבות שנותחו</span>
        </Link>
      </nav>

      <nav className="topics" aria-label="נושאים">
        <p className="rail-label">נושאים <span>כתבות שנותחו ב־7 הימים האחרונים</span></p>
        <Link to={topicTo("")} className={`topic-link${onFeed && !topic ? " active" : ""}`} onClick={scrollTop}>
          <span className="name">הכול</span>
        </Link>
        {meta.nav_topics.map((k) => (
          <Link key={k} to={topicTo(k)} className={`topic-link${topic === k ? " active" : ""}`} onClick={scrollTop}>
            <span className="name">{meta.topics[k]}</span>
            {overview?.topics[k] ? <span className="count">{overview.topics[k]}</span> : null}
          </Link>
        ))}
      </nav>

      <p className="rail-foot">אב־טיפוס ניסיוני. מוצגים כותרות וקישורים בלבד, לא תוכן הכתבות.</p>
    </header>
  );
}

const scrollTop = () => window.scrollTo({ top: 0, behavior: "smooth" });
