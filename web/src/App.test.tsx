import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
import type { Article, ArticleDetail, Meta, Overview } from "./types";

const SECRET = "טקסט פנימי סודי";

const meta: Meta = {
  outlets: { ynet: "ynet", haaretz: "הארץ" },
  topics: { politics: "פוליטיקה", security: "ביטחון" },
  nav_topics: ["politics", "security"],
  article_types: { opinion: "דעה", news: "ידיעה חדשותית" },
  leanings: { "-1": "שמאל־מרכז", "0": "מרכז / ללא נטייה", na: "לא רלוונטי פוליטית" },
  axes: [],
  timezone: "Asia/Jerusalem",
};

const axes = [
  { key: "overall", title: "סיכום שמאל–ימין", low: "שמאל", high: "ימין", min: -2, max: 2, score: -1, applicable: true, confidence: "medium" as const, confidence_he: "בינונית" },
  { key: "security", title: "ביטחון ומדיניות חוץ", low: "יוני", high: "ניצי", min: -2, max: 2, score: null, applicable: false, confidence: "high" as const, confidence_he: "גבוהה" },
];

const analyzed: Article = {
  id: 1, outlet: "ynet", outlet_name: "ynet", title: "כותרת מספר 0", url: "https://ynet.example/0", author: "דנה כהן",
  published_at: new Date().toISOString(), status: "done", status_he: "", analysis: {
    article_type: "opinion", article_type_he: "דעה", topic: "politics", topic_he: "פוליטיקה", favored_side: "left", favored_side_he: "שמאל",
    axes, explanation: "הכותב משתמש בביטוי ממשלה הרסנית.", evidence: ["ממשלה הרסנית"], summary: "טור דעה.", model: "test", analyzed_at: "",
  },
};
const paywalled: Article = {
  id: 8, outlet: "haaretz", outlet_name: "הארץ", title: "בתשלום", url: "https://haaretz.example/.premium/1", author: null,
  published_at: new Date().toISOString(), status: "paywalled", status_he: "תוכן בתשלום – לא נותח", analysis: null,
};
const detail: ArticleDetail = {
  ...analyzed,
  author_profile: { author: "דנה כהן", n: 6, shown: true, avg: -1, text: "כתבות של כותב/ת זה נוטות שמאלה, על סמך 6 כתבות שנותחו.", caveat: "הסתייגות" },
};
const overview: Overview = {
  outlets: { ynet: 7 }, topics: { politics: 6 }, last_collected: new Date().toISOString(),
  stats: { total: 8, analyzed: 6, outlets: 2, pending: 1, paywalled: 1, last_24h: 7, coverage: 75 },
  breakdown: { leaning: { "-1": 6 }, not_political: 0, types: { opinion: 6 } },
};

let requests: string[];
beforeEach(() => {
  requests = [];
  vi.stubGlobal("scrollTo", vi.fn());
  vi.stubGlobal("fetch", vi.fn(async (input: string) => {
    requests.push(input);
    const url = new URL(input, "http://x");
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
    if (url.pathname === "/api/meta") return json(meta);
    if (url.pathname === "/api/overview") return json(overview);
    if (url.pathname === "/api/articles") {
      const items = [analyzed, paywalled].filter((a) => !url.searchParams.get("analyzed") || a.analysis);
      return json({ items, offset: 0, page_size: 40 });
    }
    if (url.pathname === "/api/articles/1") return json(detail);
    if (url.pathname === "/api/articles/999") return json({ detail: "not found" }, 404);
    return json({ detail: "not found" }, 404);
  }));
});

const renderAt = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

describe("feed", () => {
  it("lists articles with Hebrew labels and a leaning strip, and never any article text", async () => {
    renderAt("/");
    expect(await screen.findByText("כותרת מספר 0")).toBeInTheDocument();
    expect(screen.getByText("בתשלום", { selector: ".card-title" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /סיכום שמאל–ימין: -1 בסולם/ })).toBeInTheDocument();
    expect(screen.getByText("שמאל־מרכז", { selector: ".lean-label" })).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(SECRET);
    expect(screen.getByText("היום")).toBeInTheDocument(); // day heading
  });

  it("reads filters from the URL, shows chips, and removes one on click", async () => {
    const user = userEvent.setup();
    renderAt("/?topic=politics&outlet=ynet&analyzed=1");
    await screen.findByText("כותרת מספר 0");
    expect(requests.some((r) => r.includes("topic=politics") && r.includes("outlet=ynet") && r.includes("analyzed=1"))).toBe(true);
    const chips = document.querySelector("#active-chips") as HTMLElement;
    expect(within(chips).getByRole("button", { name: "הסרת הסינון: פוליטיקה" })).toBeInTheDocument();
    await user.click(within(chips).getByRole("button", { name: "הסרת הסינון: ynet" }));
    await waitFor(() => expect(requests.at(-1)).not.toContain("outlet=ynet"));
    expect(within(chips).queryByRole("button", { name: "הסרת הסינון: ynet" })).toBeNull();
  });

  it("shows the empty state", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const path = String(input);
      if (path.startsWith("/api/articles")) return new Response(JSON.stringify({ items: [], offset: 0, page_size: 40 }));
      return new Response(JSON.stringify(path === "/api/meta" ? meta : overview));
    });
    renderAt("/?q=zzz");
    expect(await screen.findByText("לא נמצאו כתבות")).toBeInTheDocument();
  });

  it("reveals the stats panel only on demand", async () => {
    const user = userEvent.setup();
    renderAt("/");
    await screen.findByText("כותרת מספר 0");
    expect(screen.queryByText("במספרים")).toBeNull();
    const toggle = screen.getByRole("button", { name: /נתונים/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(await screen.findByText("במספרים")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByTitle("שמאל־מרכז: 6")).toBeInTheDocument();
  });
});

describe("drawer", () => {
  it("opens over the feed on click, shows the analysis, and closes with Escape", async () => {
    const user = userEvent.setup();
    renderAt("/");
    await user.click(await screen.findByRole("link", { name: /כותרת מספר 0/ }));

    const drawer = await screen.findByRole("dialog");
    expect(await within(drawer).findByText("למה הדירוג הזה")).toBeInTheDocument();
    expect(within(drawer).getByText("ממשלה הרסנית")).toBeInTheDocument();
    expect(within(drawer).getByText("לא רלוונטי לכתבה זו")).toBeInTheDocument(); // the security axis
    expect(within(drawer).getByText(/על סמך 6 כתבות/)).toBeInTheDocument();
    const out = within(drawer).getByRole("link", { name: /לכתבה המלאה/ });
    expect(out).toHaveAttribute("href", "https://ynet.example/0");
    expect(out).toHaveAttribute("rel", "noopener noreferrer");
    expect(drawer.textContent).not.toContain(SECRET);
    // The feed is still there behind it.
    expect(screen.getByText("בתשלום", { selector: ".card-title" })).toBeInTheDocument();

    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.getByText("כותרת מספר 0", { selector: ".card-title" })).toBeInTheDocument();
  });
});

describe("article page", () => {
  it("renders the full page for a direct link", async () => {
    renderAt("/article/1");
    expect(await screen.findByRole("heading", { level: 1, name: "כותרת מספר 0" })).toBeInTheDocument();
    expect(await screen.findByText("למה הדירוג הזה")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.title).toBe("כותרת מספר 0 · זווית");
  });

  it("says when the article doesn't exist", async () => {
    renderAt("/article/999");
    expect(await screen.findByText("הכתבה לא נמצאה")).toBeInTheDocument();
  });
});

describe("methodology", () => {
  it("fills in the live settings and marks disabled outlets", async () => {
    vi.mocked(fetch).mockImplementation(async (input) => {
      const path = String(input);
      if (path === "/api/methodology") {
        return new Response(JSON.stringify({ model: "qwen3:8b", min_author: 5, retention: 30, outlets: [{ id: "ynet", name: "ynet", enabled: true }, { id: "kan", name: "כאן חדשות", enabled: false }] }));
      }
      return new Response(JSON.stringify(path === "/api/meta" ? meta : overview));
    });
    renderAt("/methodology");
    expect(await screen.findByText(/המודל \(qwen3:8b\)/)).toBeInTheDocument();
    expect(screen.getByText(/ונמחק אחרי 30 ימים/)).toBeInTheDocument();
    expect(screen.getByText(/כאן חדשות – לא נאסף כרגע/)).toBeInTheDocument();
  });
});
