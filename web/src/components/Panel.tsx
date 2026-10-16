import { useEffect, useRef, useState } from "react";
import type { ArticleDetail } from "../types";
import { Icon } from "./Icon";
import { Scale } from "./Scale";

function CopyLink({ id }: { id: number }) {
  const [done, setDone] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  async function copy() {
    const link = `${location.origin}/article/${id}`;
    try {
      await navigator.clipboard.writeText(link);
    } catch {
      window.prompt("", link);
      return;
    }
    setDone(true);
    timer.current = window.setTimeout(() => setDone(false), 1800);
  }

  return (
    <button type="button" className="btn ghost" onClick={copy}>
      <Icon name="link" />
      <span>{done ? "הקישור הועתק" : "העתקת קישור"}</span>
    </button>
  );
}

/** The analysis itself: summary, scales, explanation, author aggregate, links. Shared by the drawer and the article page. */
export function Panel({ a }: { a: ArticleDetail }) {
  const an = a.analysis;
  const profile = a.author_profile;
  return (
    <div className="panel">
      {an ? (
        <>
          <section className="summary-box">
            <h3>בקצרה</h3>
            <p>{an.summary}</p>
          </section>

          <section aria-label="דירוגים">
            <h3>דירוגים</h3>
            <div className="axes">
              {an.axes.map((ax) => (
                <div key={ax.key} className={`axis ax-${ax.key}${ax.applicable ? "" : " na"}`}>
                  <div className="axis-head">
                    <span className="axis-title">{ax.title}</span>
                    {ax.applicable && <span className="conf">ודאות {ax.confidence_he}</span>}
                  </div>
                  {ax.applicable ? <Scale ax={ax} /> : <p className="muted small">לא רלוונטי לכתבה זו</p>}
                </div>
              ))}
            </div>
          </section>

          <section>
            <h3>למה הדירוג הזה</h3>
            <p className="explain">{an.explanation}</p>
            {an.evidence.length > 0 && (
              <ul className="evidence">
                {an.evidence.map((e) => <li key={e}><q>{e}</q></li>)}
              </ul>
            )}
          </section>
        </>
      ) : (
        <section className="summary-box muted"><p>{a.status_he}</p></section>
      )}

      {profile?.shown && (
        <section className="author">
          <h3>על הכותב/ת</h3>
          <p>{profile.text}</p>
          <p className="muted small">{profile.caveat}</p>
        </section>
      )}

      <div className="panel-foot">
        <span className="byline">
          {a.author && <>מאת <strong>{a.author}</strong> · </>}
          {a.outlet_name}
        </span>
        <span className="foot-actions">
          <CopyLink id={a.id} />
          <a className="btn" href={a.url} target="_blank" rel="noopener noreferrer">
            לכתבה המלאה ב{a.outlet_name}
            <Icon name="external" />
          </a>
        </span>
        {an && <p className="model-note">נותח אוטומטית ע״י {an.model}</p>}
      </div>
    </div>
  );
}
