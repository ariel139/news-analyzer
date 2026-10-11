import { markerPct } from "../format";
import { useData } from "../data";
import type { Axis } from "../types";

function ariaLabel(ax: Axis) {
  return `${ax.title}: ${ax.score} בסולם מ־${ax.min} (${ax.low}) עד ${ax.max} (${ax.high})`;
}

/** Rating scale. Low end on the left inside dir="ltr"; the fill runs from the neutral point to the score. */
export function Scale({ ax }: { ax: Axis }) {
  const score = ax.score as number;
  const zero = markerPct(ax.min < 0 ? 0 : ax.min, ax.min, ax.max);
  const pos = markerPct(score, ax.min, ax.max);
  const ticks = Array.from({ length: ax.max - ax.min + 1 }, (_, i) => ax.min + i);
  return (
    <div className={`scale${ax.min >= 0 ? " seq" : ""}`} dir="ltr" role="img" aria-label={ariaLabel(ax)}>
      <div className="track">
        <span className="fill" style={{ left: `${Math.min(zero, pos)}%`, width: `${Math.abs(pos - zero).toFixed(1)}%` }} />
        {ticks.map((t) => <span key={t} className="tick" style={{ left: `${markerPct(t, ax.min, ax.max)}%` }} />)}
        <span className={`marker conf-${ax.confidence}`} style={{ left: `${pos}%` }} />
      </div>
      <div className="ends"><span>{ax.low}</span><span>{ax.high}</span></div>
    </div>
  );
}

/** Five-segment overall-leaning strip used on list rows. */
export function Lean({ ov }: { ov: Axis }) {
  const { meta } = useData();
  const segments = Array.from({ length: ov.max - ov.min + 1 }, (_, i) => ov.min + i);
  return (
    <span className="lean">
      <span className={`lean-dots conf-${ov.confidence}`} dir="ltr" role="img" aria-label={ariaLabel(ov)}>
        {segments.map((t) => <i key={t} className={t === ov.score ? "on" : undefined} />)}
      </span>
      <span className="lean-label">{meta.leanings[String(ov.score)]}</span>
    </span>
  );
}
