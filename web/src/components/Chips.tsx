import { Link } from "react-router-dom";
import { useData } from "../data";
import type { Filters } from "../filters";
import { Icon } from "./Icon";

/** Removable chips for the active filters. */
export function Chips({ filters, update }: { filters: Filters; update: (mutate: (p: URLSearchParams) => void) => void }) {
  const { meta } = useData();
  const chips: { name: string; value?: string; text: string }[] = [];
  if (filters.topic) chips.push({ name: "topic", text: meta.topics[filters.topic] ?? filters.topic });
  for (const o of filters.outlets) chips.push({ name: "outlet", value: o, text: meta.outlets[o] ?? o });
  if (filters.leaning) chips.push({ name: "leaning", text: meta.leanings[filters.leaning] ?? filters.leaning });
  if (filters.type) chips.push({ name: "type", text: meta.article_types[filters.type] ?? filters.type });
  if (filters.analyzed) chips.push({ name: "analyzed", text: "רק כתבות שנותחו" });
  if (filters.q) chips.push({ name: "q", text: `״${filters.q}״` });

  function clear(name: string, value?: string) {
    update((p) => {
      if (!value) return void p.delete(name);
      const rest = p.getAll(name).filter((v) => v !== value);
      p.delete(name);
      rest.forEach((v) => p.append(name, v));
    });
  }

  return (
    <div id="active-chips" className="chips">
      {chips.map((c) => (
        <button key={c.name + (c.value ?? "")} type="button" className="chip" aria-label={`הסרת הסינון: ${c.text}`} onClick={() => clear(c.name, c.value)}>
          <span>{c.text}</span>
          <Icon name="x" />
        </button>
      ))}
      {chips.length > 1 && <Link className="chip-reset" to="/">ניקוי הכול</Link>}
    </div>
  );
}
