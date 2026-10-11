import { useState } from "react";
import { useData } from "../data";
import { count } from "../format";
import type { Overview } from "../types";
import { Icon } from "./Icon";

const maxOf = (xs: number[]) => Math.max(1, ...xs);

/** End rail: a button that reveals whole-corpus numbers and the "how to read a rating" legend. */
export function StatsRail() {
  const { overview } = useData();
  const [open, setOpen] = useState(false);
  return (
    <aside className="rail-end" aria-label="סקירה">
      <button type="button" className="stats-toggle" aria-expanded={open} aria-controls="stats-panel" onClick={() => setOpen((o) => !o)}>
        <Icon name="chart" />
        <span>נתונים</span>
        <Icon name="chevDown" className="chev" />
      </button>
      {open && (overview ? <StatsPanel ov={overview} /> : (
        <div id="stats-panel" className="stats-panel"><p className="box-sub">אין עדיין נתונים.</p></div>
      ))}
    </aside>
  );
}

function StatsPanel({ ov }: { ov: Overview }) {
  const { meta } = useData();
  const { stats, breakdown } = ov;
  const nLean = Object.values(breakdown.leaning).reduce((a, b) => a + b, 0);
  const leanTop = maxOf(Object.values(breakdown.leaning));
  const typeTop = maxOf(Object.values(breakdown.types));
  const outletRows = Object.entries(ov.outlets).filter(([id]) => id in meta.outlets).sort((a, b) => b[1] - a[1]);
  const outletTop = maxOf(outletRows.map(([, n]) => n));
  return (
    <div id="stats-panel" className="stats-panel">
      <section className="box numbers">
        <h2>במספרים</h2>
        <dl>
          <div><dt>כתבות</dt><dd>{count(stats.total)}</dd></div>
          <div><dt>נותחו</dt><dd>{count(stats.analyzed)}</dd></div>
          <div><dt>ב־24 שעות</dt><dd>{count(stats.last_24h)}</dd></div>
          <div><dt title="ממתינות לניתוח">בהמתנה</dt><dd>{count(stats.pending)}</dd></div>
          <div><dt>בתשלום</dt><dd>{count(stats.paywalled)}</dd></div>
          <div><dt>מקורות</dt><dd>{stats.outlets}</dd></div>
        </dl>
        <div className="meter" role="img" aria-label={`${stats.coverage}% מהכתבות נותחו`}>
          <span className="meter-bar"><i style={{ width: `${stats.coverage}%` }} /></span>
          <span className="meter-text"><strong>{stats.coverage}%</strong> מהכתבות נותחו</span>
        </div>
      </section>

      {nLean > 0 && (
        <section className="box">
          <h2>נטייה כללית</h2>
          <p className="box-sub">{nLean} כתבות שנותחו ב־7 הימים האחרונים. דירוג אוטומטי, לא קביעה.</p>
          <ol className="hist ax-overall" dir="ltr">
            {[-2, -1, 0, 1, 2].map((score) => {
              const n = breakdown.leaning[String(score)] ?? 0;
              const label = `${meta.leanings[String(score)]}: ${n}`;
              return (
                <li key={score} title={label} aria-label={label}>
                  <span className="hist-n">{n}</span>
                  <span className="hist-col"><i style={{ height: `${((n / leanTop) * 100).toFixed(1)}%` }} /></span>
                </li>
              );
            })}
          </ol>
          <div className="ends" dir="ltr"><span>שמאל</span><span>מרכז</span><span>ימין</span></div>
          {breakdown.not_political > 0 && <p className="box-sub after">ועוד {breakdown.not_political} כתבות לא רלוונטיות פוליטית</p>}
        </section>
      )}

      {Object.keys(breakdown.types).length > 0 && (
        <section className="box">
          <h2>סוגי כתבות</h2>
          <p className="box-sub">כתבות שנותחו ב־7 הימים האחרונים</p>
          <ul className="bars">
            {Object.entries(breakdown.types).map(([k, n]) => (
              <li key={k}>
                <span className="name">{meta.article_types[k] ?? k}</span>
                <span className="bar" aria-hidden="true"><i style={{ width: `${((n / typeTop) * 100).toFixed(1)}%` }} /></span>
                <span className="count">{n}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {outletRows.length > 0 && (
        <section className="box">
          <h2>כתבות לפי מקור</h2>
          <p className="box-sub">נאספו ב־24 השעות האחרונות</p>
          <ul className="bars">
            {outletRows.map(([id, n]) => (
              <li key={id}>
                <span className="name">{meta.outlets[id]}</span>
                <span className="bar" aria-hidden="true"><i style={{ width: `${((n / outletTop) * 100).toFixed(1)}%` }} /></span>
                <span className="count">{n}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="box">
        <h2>איך לקרוא את הדירוג</h2>
        <div className="legend">
          <div className="legend-scale ax-overall" dir="ltr" aria-hidden="true">
            <span className="lg-track" /><span className="lg-fill" /><span className="lg-dot" />
          </div>
          <ul className="legend-list">
            <li><span className="lg-sample solid" aria-hidden="true" />ודאות גבוהה</li>
            <li><span className="lg-sample light" aria-hidden="true" />ודאות בינונית</li>
            <li><span className="lg-sample dashed" aria-hidden="true" />ודאות נמוכה</li>
          </ul>
          <p>הפס הצבוע נמתח מהאמצע אל הדירוג: ארוך יותר פירושו נטייה חזקה יותר. לכל ציר צבע משלו, והצבע אינו מסמן צד.</p>
        </div>
      </section>
    </div>
  );
}
