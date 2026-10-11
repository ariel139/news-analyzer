// Dates are shown in the site's timezone (from /api/meta), whatever the visitor's own zone is.
const WEEKDAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]; // Date.getDay() order
const EN_WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const formatters = new Map<string, Intl.DateTimeFormat>();

export interface LocalParts {
  year: string;
  month: string;
  day: string;
  hour: string;
  minute: string;
  weekday: number;
}

export function localParts(date: Date, tz: string): LocalParts {
  let f = formatters.get(tz);
  if (!f) {
    f = new Intl.DateTimeFormat("en-GB", {
      timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23", weekday: "short",
    });
    formatters.set(tz, f);
  }
  const p = Object.fromEntries(f.formatToParts(date).map((x) => [x.type, x.value]));
  return { year: p.year, month: p.month, day: p.day, hour: p.hour, minute: p.minute, weekday: EN_WEEKDAYS.indexOf(p.weekday) };
}

/** 10.10.2026 21:04 */
export function fullDate(iso: string, tz: string): string {
  const p = localParts(new Date(iso), tz);
  return `${p.day}.${p.month}.${p.year} ${p.hour}:${p.minute}`;
}

/** 'לפני 5 דק׳' for recent items, otherwise a local date. */
export function relTime(iso: string, tz: string, now: number = Date.now()): string {
  const minutes = Math.floor((now - new Date(iso).getTime()) / 60_000);
  if (minutes < 1) return "עכשיו";
  if (minutes < 60) return `לפני ${minutes} דק׳`;
  if (minutes < 24 * 60) {
    const h = Math.floor(minutes / 60);
    return h === 1 ? "לפני שעה" : `לפני ${h} שעות`;
  }
  const p = localParts(new Date(iso), tz);
  return `${p.day}.${p.month} ${p.hour}:${p.minute}`;
}

/** YYYY-MM-DD in the site timezone: the key feed items are grouped under. */
export function dayKey(iso: string | number, tz: string): string {
  const p = localParts(new Date(iso), tz);
  return `${p.year}-${p.month}-${p.day}`;
}

/** Feed section heading: 'היום', 'אתמול', or 'יום חמישי, 8.10'. */
export function dayLabel(key: string, tz: string, now: number = Date.now()): string {
  if (key === dayKey(now, tz)) return "היום";
  const [y, m, d] = key.split("-").map(Number);
  const utc = Date.UTC(y, m - 1, d);
  if (key === dayKey(now - 24 * 3600_000, tz)) return "אתמול";
  return `יום ${WEEKDAYS[new Date(utc).getUTCDay()]}, ${d}.${m}`;
}

export const count = (n: number) => n.toLocaleString("en-US");

/** Position of a score on its scale, 0-100, one decimal. */
export function markerPct(score: number, lo: number, hi: number): number {
  return Math.round(((score - lo) / (hi - lo)) * 1000) / 10;
}
