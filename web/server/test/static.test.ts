import assert from "node:assert/strict";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { startServer } from "./helpers.ts";

test("serves the built app with an SPA fallback, but API 404s stay JSON", async () => {
  const probe = await startServer();
  const dist = path.join(probe.dir, "dist");
  await probe.close();
  mkdirSync(path.join(dist, "assets"), { recursive: true });
  writeFileSync(path.join(dist, "index.html"), "<!doctype html><div id=root></div>");
  writeFileSync(path.join(dist, "assets", "app-abc.js"), "console.log(1)");
  const s = await startServer({ clientDir: dist });
  try {
    const home = await fetch(s.base + "/article/5"); // client-side route
    assert.equal(home.status, 200);
    assert.match(await home.text(), /id=root/);
    assert.equal(home.headers.get("cache-control"), "no-cache");
    const asset = await fetch(s.base + "/assets/app-abc.js");
    assert.match(asset.headers.get("cache-control") ?? "", /immutable/);
    const api = await fetch(s.base + "/api/missing");
    assert.equal(api.status, 404);
    assert.equal(api.headers.get("content-type")?.includes("json"), true);
  } finally {
    await s.close();
  }
});
