/** Author leaning aggregates. Never a label on a person: a statistic about rated articles, with N. */
import type { DatabaseSync } from "node:sqlite";
import { authorOverallScores } from "./db.ts";

export const CAVEAT =
  "נתון זה מבוסס על דירוג אוטומטי של מודל בינה מלאכותית לכתבות בלבד, במדגם קטן. " +
  "הוא אינו מעיד על עמדותיו האישיות של הכותב/ת, ועשוי לשקף את סוג הנושאים שעליהם הוא/היא כותב/ת.";

export function leanPhrase(avg: number): string {
  if (avg <= -1.0) return "שמאלה";
  if (avg <= -0.4) return "מעט שמאלה";
  if (avg < 0.4) return "למרכז, ללא נטייה ברורה";
  if (avg < 1.0) return "מעט ימינה";
  return "ימינה";
}

export function isPerson(author: string | null, nonPerson: string[]): author is string {
  if (!author || author.length < 4) return false;
  const low = author.toLowerCase();
  return !nonPerson.some((p) => low.includes(p.toLowerCase()));
}

export type AuthorProfile =
  | { author: string; n: number; shown: false; min: number }
  | { author: string; n: number; shown: true; avg: number; text: string; caveat: string };

/** null if no (person) author. The text is included only when n >= minArticles. */
export function authorProfile(
  conn: DatabaseSync,
  author: string | null,
  opts: { minArticles: number; nonPerson: string[] },
): AuthorProfile | null {
  if (!isPerson(author, opts.nonPerson)) return null;
  const scores = authorOverallScores(conn, author);
  const n = scores.length;
  if (n < opts.minArticles) return { author, n, shown: false, min: opts.minArticles };
  const avg = scores.reduce((a, b) => a + b, 0) / n;
  return {
    author,
    n,
    shown: true,
    avg: Math.round(avg * 100) / 100,
    text: `כתבות של כותב/ת זה נוטות ${leanPhrase(avg)}, על סמך ${n} כתבות שנותחו.`,
    caveat: CAVEAT,
  };
}
