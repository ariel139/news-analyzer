import { useEffect, type ReactNode } from "react";
import { Rail } from "./Rail";

/** Page chrome: skip link, start rail, main column and an optional end rail. */
export function Shell({ title, end, children }: { title?: string; end?: ReactNode; children: ReactNode }) {
  useEffect(() => {
    document.title = title ? `${title} · זווית` : "זווית";
  }, [title]);

  return (
    <>
      <a className="skip" href="#main">דילוג לתוכן</a>
      <div className={`shell${end ? "" : " no-end"}`}>
        <Rail />
        <main className="main" id="main">{children}</main>
        {end}
      </div>
    </>
  );
}
