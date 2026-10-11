/** Runtime settings from NA_* env vars (the same names the Python side uses) and the outlet registry. */
import { readFileSync } from "node:fs";
import path from "node:path";
import { parse } from "yaml";

export const ROOT = process.env.NA_ROOT ?? path.resolve(import.meta.dirname, "..", "..");

export interface Settings {
  dbPath: string;
  outletsFile: string;
  clientDir: string;
  timezone: string;
  authorMinArticles: number;
  llmModel: string;
  textRetentionDays: number;
  host: string;
  port: number;
}

export interface Outlet {
  id: string;
  name: string;
  enabled: boolean;
}

export interface OutletRegistry {
  outlets: Outlet[];
  nonPersonAuthors: string[];
  enabled(): Outlet[];
  nameOf(id: string): string;
}

const abs = (p: string) => (path.isAbsolute(p) ? p : path.resolve(ROOT, p));

function int(v: string | undefined, fallback: number): number {
  const n = Number.parseInt(v ?? "", 10);
  return Number.isFinite(n) ? n : fallback;
}

export function loadSettings(env: NodeJS.ProcessEnv = process.env): Settings {
  return {
    dbPath: abs(env.NA_DB_PATH ?? "data/news.db"),
    outletsFile: abs(env.NA_OUTLETS_FILE ?? "config/outlets.yaml"),
    clientDir: abs(env.NA_WEB_DIST ?? "web/dist"),
    timezone: env.NA_TIMEZONE ?? "Asia/Jerusalem",
    authorMinArticles: int(env.NA_AUTHOR_MIN_ARTICLES, 5),
    llmModel: env.NA_LLM_MODEL ?? "qwen3:8b",
    textRetentionDays: int(env.NA_TEXT_RETENTION_DAYS, 30),
    host: env.NA_WEB_HOST ?? "127.0.0.1",
    port: int(env.NA_WEB_PORT, 8000),
  };
}

export function loadOutlets(file: string): OutletRegistry {
  const raw = (parse(readFileSync(file, "utf-8")) ?? {}) as {
    outlets?: { id: string; name?: string; enabled?: boolean }[];
    non_person_authors?: string[];
  };
  const outlets = (raw.outlets ?? []).map((o) => ({ id: o.id, name: o.name ?? o.id, enabled: o.enabled ?? true }));
  return {
    outlets,
    nonPersonAuthors: raw.non_person_authors ?? [],
    enabled: () => outlets.filter((o) => o.enabled),
    nameOf: (id) => outlets.find((o) => o.id === id)?.name ?? id,
  };
}
