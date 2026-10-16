import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";
import { SECRET, startServer } from "./helpers.ts";

let s: Awaited<ReturnType<typeof startServer>>;
before(async () => {
  s = await startServer();
  s.seed();
});
after(() => s.close());

const items = async (qs: string) => (await s.get(`/api/articles${qs}`)).json().items as any[];

describe("articles", () => {
  test("lists newest first and never exposes article text", async () => {
    const r = await s.get("/api/articles");
    assert.equal(r.status, 200);
    const list = r.json().items;
    assert.equal(list.length, 8);
    assert.ok(!r.text.includes(SECRET));
    assert.ok(list[0].published_at >= list.at(-1).published_at);
  });

  test("filters", async () => {
    assert.deepEqual(new Set((await items("?outlet=haaretz")).map((i) => i.outlet)), new Set(["haaretz"]));
    assert.equal((await items("?leaning=-1")).length, 6);
    assert.equal((await items("?leaning=2")).length, 0);
    assert.equal((await items("?type=opinion&topic=politics")).length, 6);
    const analyzed = await items("?analyzed=1");
    assert.equal(analyzed.length, 6);
    assert.ok(analyzed.every((a) => a.analysis));
  });

  test("several outlets, with a cap", async () => {
    assert.equal((await items("?outlet=ynet&outlet=haaretz")).length, 8);
    const many = Array.from({ length: 21 }, (_, i) => `outlet=o${i}`).join("&");
    assert.equal((await s.get(`/api/articles?${many}`)).status, 422);
  });

  test("invalid input is rejected", async () => {
    assert.equal((await s.get("/api/articles?leaning=7")).status, 422);
    assert.equal((await s.get("/api/articles?offset=-1")).status, 422);
    assert.equal((await s.get("/api/articles?analyzed=maybe")).status, 422);
    assert.equal((await s.get(`/api/articles?q=${"x".repeat(81)}`)).status, 422);
  });

  test("headline search treats % and _ literally", async () => {
    assert.equal((await items("?q=" + encodeURIComponent("מספר 3"))).length, 1);
    assert.equal((await items("?q=" + encodeURIComponent("100%"))).length, 0);
    assert.equal((await items("?q=" + encodeURIComponent("כותרת"))).length, 7);
  });

  test("paging", async () => {
    assert.equal((await items("?offset=7")).length, 1);
    assert.equal((await items("?offset=8")).length, 0);
  });
});

describe("article detail", () => {
  test("analysis, Hebrew labels and author profile", async () => {
    const r = await s.get("/api/articles/1");
    const d = r.json();
    assert.ok(!r.text.includes(SECRET));
    assert.equal(d.analysis.article_type_he, "דעה");
    assert.equal(d.analysis.favored_side, "left");
    assert.equal(d.analysis.favored_side_he, "שמאל");
    const overall = d.analysis.axes.find((a: any) => a.key === "overall");
    assert.equal(overall.score, -1);
    assert.equal(overall.confidence_he, "בינונית");
    const security = d.analysis.axes.find((a: any) => a.key === "security");
    assert.equal(security.applicable, false);
    assert.deepEqual(d.analysis.evidence, ["ממשלה הרסנית"]);
    assert.ok(d.author_profile.shown && d.author_profile.n === 6);
    assert.match(d.author_profile.text, /על סמך 6 כתבות/);
  });

  test("paywalled article has no analysis or profile", async () => {
    const d = (await s.get("/api/articles/8")).json();
    assert.equal(d.analysis, null);
    assert.equal(d.status, "paywalled");
    assert.equal(d.author_profile, null);
    assert.match(d.status_he, /תוכן בתשלום/);
  });

  test("404 and 422", async () => {
    assert.equal((await s.get("/api/articles/999")).status, 404);
    assert.equal((await s.get("/api/articles/abc")).status, 422);
  });
});

describe("author profile threshold", () => {
  test("hidden below the minimum, and desks are not people", async () => {
    const strict = await startServer({ authorMinArticles: 10 });
    strict.seed();
    try {
      const p = (await strict.get("/api/articles/1")).json().author_profile;
      assert.deepEqual(p, { author: "דנה כהן", n: 6, shown: false, min: 10 });
    } finally {
      await strict.close();
    }
  });
});

describe("overview, new, meta, methodology", () => {
  test("overview numbers", async () => {
    const o = (await s.get("/api/overview")).json();
    assert.equal(o.stats.total, 8);
    assert.equal(o.stats.analyzed, 6);
    assert.equal(o.stats.pending, 1);
    assert.equal(o.stats.paywalled, 1);
    assert.equal(o.stats.coverage, 75);
    assert.equal(o.stats.outlets, 2);
    assert.equal(o.topics.politics, 6);
    assert.equal(o.breakdown.leaning["-1"], 6);
    assert.equal(o.breakdown.types.opinion, 6);
    assert.ok(o.last_collected);
  });

  test("new-article count", async () => {
    assert.equal((await s.get("/api/new?since=" + encodeURIComponent("2000-01-01T00:00:00+00:00"))).json().n, 8);
    assert.equal((await s.get("/api/new?since=" + encodeURIComponent("2999-01-01T00:00:00+00:00"))).json().n, 0);
    assert.equal((await s.get("/api/new?since=nope")).status, 422);
    assert.equal((await s.get("/api/new")).status, 422);
  });

  test("meta lists enabled outlets only", async () => {
    const m = (await s.get("/api/meta")).json();
    assert.deepEqual(m.outlets, { ynet: "ynet", haaretz: "הארץ" });
    assert.equal(m.axes.length, 5);
    assert.ok(m.nav_topics.includes("politics") && !m.nav_topics.includes("sports"));
    assert.equal(m.leanings.na, "לא רלוונטי פוליטית");
  });

  test("methodology includes disabled outlets", async () => {
    const m = (await s.get("/api/methodology")).json();
    assert.equal(m.model, "test-model");
    assert.equal(m.outlets.length, 3);
    assert.equal(m.outlets.find((o: any) => o.id === "kan").enabled, false);
  });

  test("health and unknown API routes", async () => {
    assert.deepEqual((await s.get("/healthz")).json(), { ok: true });
    assert.equal((await s.get("/api/nope")).status, 404);
  });
});

describe("before the Python side has created the DB", () => {
  test("503 for data routes, 200 for static ones", async () => {
    const empty = await startServer();
    try {
      assert.equal((await empty.get("/api/articles")).status, 503);
      assert.equal((await empty.get("/api/meta")).status, 200);
      empty.seed(); // the worker creates it later; the server picks it up without a restart
      assert.equal((await empty.get("/api/articles")).status, 200);
    } finally {
      await empty.close();
    }
  });
});
