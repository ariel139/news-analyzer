/** Express app: JSON API under /api, plus the built React app (SPA) for everything else. */
import { existsSync } from "node:fs";
import path from "node:path";
import type { DatabaseSync } from "node:sqlite";
import express, { type NextFunction, type Request, type Response } from "express";
import { authorProfile } from "./authors.ts";
import type { OutletRegistry, Settings } from "./config.ts";
import * as db from "./db.ts";
import * as labels from "./labels.ts";
import { articleDto } from "./serialize.ts";

export const PAGE_SIZE = 40;
const MAX_OUTLETS = 20;
const LEANING = /^(-2|-1|0|1|2|na)?$/;
const HOUR = 3600_000;

class HttpError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Last value of a query param that must be a single string. */
function one(v: unknown, name: string, maxLen: number): string | undefined {
  const s = Array.isArray(v) ? v[v.length - 1] : v;
  if (s === undefined) return undefined;
  if (typeof s !== "string" || s.length > maxLen) throw new HttpError(422, `invalid ${name}`);
  return s;
}

function bool(v: unknown, name: string): boolean {
  const s = one(v, name, 10)?.toLowerCase();
  if (s === undefined || ["", "0", "false", "off", "no", "n", "f"].includes(s)) return false;
  if (["1", "true", "on", "yes", "y", "t"].includes(s)) return true;
  throw new HttpError(422, `invalid ${name}`);
}

export function parseFilters(query: Request["query"]): db.FeedFilters {
  const raw = query.outlet === undefined ? [] : Array.isArray(query.outlet) ? query.outlet : [query.outlet];
  if (raw.length > MAX_OUTLETS || raw.some((o) => typeof o !== "string" || o.length > 40)) {
    throw new HttpError(422, "invalid outlet");
  }
  const outlets = [...new Set((raw as string[]).filter(Boolean))]; // dedupe, keep order

  const topic = one(query.topic, "topic", 40);
  const type = one(query.type, "type", 20);
  const leaning = one(query.leaning, "leaning", 10);
  if (leaning !== undefined && !LEANING.test(leaning)) throw new HttpError(422, "invalid leaning");
  const offsetRaw = one(query.offset, "offset", 10);
  const offset = offsetRaw === undefined ? 0 : Number(offsetRaw);
  if (!Number.isInteger(offset) || offset < 0 || offset > 100_000) throw new HttpError(422, "invalid offset");

  return {
    outlets,
    topic: topic && topic in labels.TOPICS ? topic : undefined,
    leaning: leaning || undefined,
    type: type && type in labels.ARTICLE_TYPES ? type : undefined,
    analyzed: bool(query.analyzed, "analyzed"),
    q: one(query.q, "q", 80)?.trim() || undefined,
    offset,
  };
}

export interface AppDeps {
  settings: Settings;
  outlets: OutletRegistry;
  getDb: () => DatabaseSync | null;
}

export function createApp({ settings, outlets, getDb }: AppDeps) {
  const app = express();
  app.disable("x-powered-by");
  app.use((_req, res, next) => {
    res.setHeader("X-Content-Type-Options", "nosniff");
    res.setHeader("Referrer-Policy", "same-origin");
    next();
  });

  const api = express.Router();
  api.use((_req, res, next) => {
    res.setHeader("Cache-Control", "no-store");
    next();
  });
  /** Handlers that read the DB get it as an argument; 503 until the Python side has created it. */
  const withDb =
    (fn: (conn: DatabaseSync, req: Request, res: Response) => void) => (req: Request, res: Response) => {
      const conn = getDb();
      if (!conn) throw new HttpError(503, "database not ready");
      fn(conn, req, res);
    };
  const profileOf = (conn: DatabaseSync, author: string | null) =>
    authorProfile(conn, author, { minArticles: settings.authorMinArticles, nonPerson: outlets.nonPersonAuthors });

  app.get("/healthz", (_req, res) => void res.json({ ok: true }));

  api.get("/meta", (_req, res) => {
    res.json({
      outlets: Object.fromEntries(outlets.enabled().map((o) => [o.id, o.name])),
      topics: labels.TOPICS,
      nav_topics: labels.NAV_TOPICS,
      article_types: labels.ARTICLE_TYPES,
      leanings: labels.LEANINGS,
      axes: labels.AXES,
      timezone: settings.timezone,
    });
  });

  api.get("/articles", withDb((conn, req, res) => {
    const f = parseFilters(req.query);
    res.json({ items: db.queryFeed(conn, f, PAGE_SIZE).map((r) => articleDto(r, outlets)), offset: f.offset, page_size: PAGE_SIZE });
  }));

  api.get("/articles/:id", withDb((conn, req, res) => {
    const id = Number(req.params.id);
    if (!Number.isInteger(id)) throw new HttpError(422, "invalid id");
    const row = db.getArticle(conn, id);
    if (!row) throw new HttpError(404, "not found");
    res.json({ ...articleDto(row, outlets), author_profile: profileOf(conn, row.author as string | null) });
  }));

  /** Sidebar numbers, stats panel and topic counts in one call. */
  api.get("/overview", withDb((conn, _req, res) => {
    const now = Date.now();
    const ov = db.feedOverview(conn, db.isoSec(new Date(now - 24 * HOUR)), db.isoSec(new Date(now - 7 * 24 * HOUR)));
    const byStatus = db.statusCounts(conn);
    const total = Object.values(byStatus).reduce((a, b) => a + b, 0);
    const done = byStatus.done ?? 0;
    res.json({
      ...ov,
      stats: {
        total,
        analyzed: done,
        outlets: outlets.enabled().length,
        pending: byStatus.pending ?? 0,
        paywalled: byStatus.paywalled ?? 0,
        last_24h: Object.values(ov.outlets).reduce((a, b) => a + b, 0),
        coverage: total ? Math.round((done / total) * 100) : 0,
      },
      breakdown: db.analysisBreakdown(conn, db.isoSec(new Date(now - 7 * 24 * HOUR))),
    });
  }));

  /** Polled by the feed page: how many articles were collected since it loaded. */
  api.get("/new", withDb((conn, req, res) => {
    const since = one(req.query.since, "since", 40);
    if (!since || Number.isNaN(Date.parse(since))) throw new HttpError(422, "invalid since");
    res.json({ n: db.countCollectedAfter(conn, since) });
  }));

  api.get("/methodology", (_req, res) => {
    res.json({
      model: settings.llmModel,
      min_author: settings.authorMinArticles,
      retention: settings.textRetentionDays,
      outlets: outlets.outlets.map((o) => ({ id: o.id, name: o.name, enabled: o.enabled })),
    });
  });

  api.use((_req, _res, next) => next(new HttpError(404, "not found")));
  app.use("/api", api);

  // The built React app. Hashed files under /assets cache forever; index.html never does.
  const indexHtml = path.join(settings.clientDir, "index.html");
  if (existsSync(indexHtml)) {
    app.use(express.static(settings.clientDir, {
      index: false,
      setHeaders: (res, file) => {
        res.setHeader("Cache-Control", file.includes(`${path.sep}assets${path.sep}`) ? "public, max-age=31536000, immutable" : "no-cache");
      },
    }));
    app.get(/^(?!\/api\/).*/, (_req, res) => {
      res.setHeader("Cache-Control", "no-cache");
      res.sendFile(indexHtml);
    });
  }

  app.use((err: unknown, _req: Request, res: Response, _next: NextFunction) => {
    if (err instanceof HttpError) {
      res.status(err.status).json({ detail: err.message });
      return;
    }
    console.error(err);
    res.status(500).json({ detail: "internal error" });
  });
  return app;
}
