import { mkdtempSync, readFileSync } from "node:fs";
import type { AddressInfo } from "node:net";
import os from "node:os";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import { createApp } from "../app.ts";
import type { OutletRegistry, Settings } from "../config.ts";
import { dbOpener, isoSec } from "../db.ts";

export const SECRET = "טקסט פנימי סודי";

/** The schema comes straight from the Python module that owns it, so the two can't drift. */
function pythonSchema(): string {
  const src = readFileSync(path.resolve(import.meta.dirname, "../../../src/news_analyzer/db.py"), "utf-8");
  const m = src.match(/^SCHEMA = """([\s\S]*?)"""/m);
  if (!m) throw new Error("SCHEMA not found in db.py");
  return m[1];
}

const registry: OutletRegistry = {
  outlets: [
    { id: "ynet", name: "ynet", enabled: true },
    { id: "haaretz", name: "הארץ", enabled: true },
    { id: "kan", name: "כאן חדשות", enabled: false },
  ],
  nonPersonAuthors: ["ynet", "מערכת"],
  enabled() { return this.outlets.filter((o) => o.enabled); },
  nameOf(id) { return this.outlets.find((o) => o.id === id)?.name ?? id; },
};

const ANALYSIS = {
  article_type: "opinion", topic: "politics", favored_side: "left",
  security_score: null, security_conf: "high", religion_score: null, religion_conf: "high",
  economy_score: null, economy_conf: "high", tone_score: 3, tone_conf: "high",
  overall_score: -1, overall_conf: "medium",
  explanation: "הכותב משתמש בביטוי ממשלה הרסנית ומציג רק צד אחד של הוויכוח.",
  evidence: JSON.stringify(["ממשלה הרסנית"]),
  summary: "טור דעה הקורא להחלפת הממשלה בטענה שמדיניותה פוגעת במוסדות המדינה ובאזרחים.",
};

/** 7 ynet articles by one author (6 analyzed, 1 pending) plus 1 paywalled haaretz article. */
export function seedDb(file: string): void {
  const conn = new DatabaseSync(file);
  conn.exec("PRAGMA journal_mode = WAL");
  conn.exec(pythonSchema());
  const now = Date.now();
  const ins = conn.prepare(
    `INSERT INTO articles (outlet, url, title, title_key, author, published_at, collected_at, analysis_text, status)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  );
  const ts = isoSec(new Date(now));
  for (let i = 0; i < 7; i++) {
    ins.run("ynet", `https://ynet.example/${i}`, `כותרת מספר ${i}`, `k${i}`, "דנה כהן", isoSec(new Date(now - i * 60_000)), ts, SECRET, i < 6 ? "done" : "pending");
  }
  ins.run("haaretz", "https://haaretz.example/.premium/1", "בתשלום", "kp", null, ts, ts, null, "paywalled");
  const cols = ["article_id", "model", "prompt_version", "created_at", "raw_json", ...Object.keys(ANALYSIS)];
  const insA = conn.prepare(`INSERT INTO analyses (${cols.join(", ")}) VALUES (${cols.map(() => "?").join(", ")})`);
  for (let id = 1; id <= 6; id++) insA.run(id, "test", "v1", ts, "{}", ...Object.values(ANALYSIS));
  conn.close();
}

export async function startServer(overrides: Partial<Settings> = {}) {
  const dir = mkdtempSync(path.join(os.tmpdir(), "na-web-"));
  const dbPath = path.join(dir, "t.db");
  const settings: Settings = {
    dbPath, outletsFile: "", clientDir: path.join(dir, "no-dist"), timezone: "Asia/Jerusalem",
    authorMinArticles: 5, llmModel: "test-model", textRetentionDays: 30, host: "127.0.0.1", port: 0,
    ...overrides,
  };
  const getDb = dbOpener(dbPath);
  const server = createApp({ settings, outlets: registry, getDb }).listen(0, "127.0.0.1");
  await new Promise((r) => server.once("listening", r));
  const base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  return {
    base, dbPath, dir, seed: () => seedDb(dbPath),
    get: async (p: string) => {
      const r = await fetch(base + p);
      const text = await r.text();
      return { status: r.status, text, json: () => JSON.parse(text) };
    },
    close: () => new Promise<void>((r) => { server.closeAllConnections(); server.close(() => r()); }),
  };
}
