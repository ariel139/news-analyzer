import path from "node:path";
import { createApp } from "./app.ts";
import { loadOutlets, loadSettings, ROOT } from "./config.ts";
import { dbOpener } from "./db.ts";

try {
  process.loadEnvFile(path.join(ROOT, ".env")); // same .env the Python side reads; real env vars win
} catch {
  // no .env: defaults apply
}

const settings = loadSettings();
const app = createApp({ settings, outlets: loadOutlets(settings.outletsFile), getDb: dbOpener(settings.dbPath) });
app.listen(settings.port, settings.host, () => {
  console.log(`news_analyzer web: http://${settings.host}:${settings.port}  (db: ${settings.dbPath})`);
});
