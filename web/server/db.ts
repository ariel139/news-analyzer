/**
 * Read-only access to the SQLite DB that the Python collector/worker writes.
 * The schema and every write live in src/news_analyzer/db.py; this side never modifies the DB.
 * `analysis_text` is LLM input only and must never be selected here.
 */
import { existsSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";

export type Row = Record<string, string | number | null>;
export type Param = string | number;

// Columns safe to expose. analysis_text is deliberately absent.
export const PUBLIC_ARTICLE_COLS =
  "a.id, a.outlet, a.url, a.title, a.author, a.published_at, a.excerpt, a.status, a.skip_reason";
export const ANALYSIS_COLS =
  "an.article_type, an.topic, an.favored_side, an.security_score, an.security_conf, an.religion_score, " +
  "an.religion_conf, an.economy_score, an.economy_conf, an.tone_score, an.tone_conf, " +
  "an.overall_score, an.overall_conf, an.explanation, an.evidence, an.summary, an.model, " +
  "an.created_at AS analyzed_at";

/** Opens the DB lazily: it may not exist yet when the site starts before the first collection. */
export function dbOpener(path: string): () => DatabaseSync | null {
  let conn: DatabaseSync | null = null;
  return () => {
    if (!conn && existsSync(path)) conn = new DatabaseSync(path, { readOnly: true, timeout: 5000 });
    return conn;
  };
}

/** Same format the Python side stores: UTC, seconds, "+00:00" (so string comparison works). */
export const isoSec = (d: Date): string => d.toISOString().replace(/\.\d{3}Z$/, "+00:00");

export interface FeedFilters {
  outlets: string[];
  topic?: string;
  leaning?: string;
  type?: string;
  analyzed: boolean;
  q?: string;
  offset: number;
}

export function queryFeed(conn: DatabaseSync, f: FeedFilters, limit: number): Row[] {
  const where: string[] = [];
  const params: Param[] = [];
  if (f.q) {
    const escaped = f.q.replaceAll("!", "!!").replaceAll("%", "!%").replaceAll("_", "!_");
    where.push("a.title LIKE ? ESCAPE '!'");
    params.push(`%${escaped}%`);
  }
  if (f.analyzed) where.push("an.article_id IS NOT NULL");
  if (f.outlets.length) {
    where.push(`a.outlet IN (${f.outlets.map(() => "?").join(", ")})`);
    params.push(...f.outlets);
  }
  if (f.topic) {
    where.push("an.topic = ?");
    params.push(f.topic);
  }
  if (f.type) {
    where.push("an.article_type = ?");
    params.push(f.type);
  }
  if (f.leaning === "na") where.push("an.article_id IS NOT NULL AND an.overall_score IS NULL");
  else if (f.leaning) {
    where.push("an.overall_score = ?");
    params.push(Number(f.leaning));
  }
  let sql = `SELECT ${PUBLIC_ARTICLE_COLS}, ${ANALYSIS_COLS} FROM articles a LEFT JOIN analyses an ON an.article_id = a.id`;
  if (where.length) sql += " WHERE " + where.join(" AND ");
  sql += " ORDER BY a.published_at DESC LIMIT ? OFFSET ?";
  return conn.prepare(sql).all(...params, limit, f.offset) as Row[];
}

export function getArticle(conn: DatabaseSync, id: number): Row | undefined {
  return conn
    .prepare(
      `SELECT ${PUBLIC_ARTICLE_COLS}, ${ANALYSIS_COLS} FROM articles a
       LEFT JOIN analyses an ON an.article_id = a.id WHERE a.id = ?`,
    )
    .get(id) as Row | undefined;
}

/** Overall scores of an author's analyzed articles (low-confidence and N/A excluded). */
export function authorOverallScores(conn: DatabaseSync, author: string): number[] {
  const rows = conn
    .prepare(
      `SELECT an.overall_score AS s FROM articles a JOIN analyses an ON an.article_id = a.id
       WHERE a.author = ? AND an.overall_score IS NOT NULL AND an.overall_conf != 'low'`,
    )
    .all(author) as { s: number }[];
  return rows.map((r) => r.s);
}

const pairs = (rows: unknown[]): Record<string, number> =>
  Object.fromEntries((rows as { k: string | number; n: number }[]).map((r) => [String(r.k), r.n]));

export function statusCounts(conn: DatabaseSync): Record<string, number> {
  return pairs(conn.prepare("SELECT status AS k, COUNT(*) AS n FROM articles GROUP BY status").all());
}

/** Per-outlet article counts and per-topic analyzed counts for the sidebar, plus the last collection time. */
export function feedOverview(conn: DatabaseSync, outletsSince: string, topicsSince: string) {
  const outlets = pairs(
    conn.prepare("SELECT outlet AS k, COUNT(*) AS n FROM articles WHERE published_at >= ? GROUP BY outlet").all(outletsSince),
  );
  const topics = pairs(
    conn
      .prepare(
        `SELECT an.topic AS k, COUNT(*) AS n FROM analyses an JOIN articles a ON a.id = an.article_id
         WHERE a.published_at >= ? GROUP BY an.topic ORDER BY COUNT(*) DESC`,
      )
      .all(topicsSince),
  );
  const last = conn.prepare("SELECT MAX(collected_at) AS m FROM articles").get() as { m: string | null };
  return { outlets, topics, last_collected: last.m };
}

/** Whole-corpus aggregates for the stats panel: overall leaning and article type in the window.
 *  Never per outlet or author. */
export function analysisBreakdown(conn: DatabaseSync, since: string) {
  const base = "FROM analyses an JOIN articles a ON a.id = an.article_id WHERE a.published_at >= ?";
  const leaning = pairs(
    conn.prepare(`SELECT an.overall_score AS k, COUNT(*) AS n ${base} AND an.overall_score IS NOT NULL GROUP BY an.overall_score`).all(since),
  );
  const notPolitical = (conn.prepare(`SELECT COUNT(*) AS n ${base} AND an.overall_score IS NULL`).get(since) as { n: number }).n;
  const types = pairs(
    conn.prepare(`SELECT an.article_type AS k, COUNT(*) AS n ${base} GROUP BY an.article_type ORDER BY COUNT(*) DESC`).all(since),
  );
  return { leaning, not_political: notPolitical, types };
}

export function countCollectedAfter(conn: DatabaseSync, since: string): number {
  return (conn.prepare("SELECT COUNT(*) AS n FROM articles WHERE collected_at > ?").get(since) as { n: number }).n;
}
