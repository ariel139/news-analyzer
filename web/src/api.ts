import type { ArticleDetail, Article, Meta, Methodology, Overview } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch(path, { signal, headers: { Accept: "application/json" } });
  if (!r.ok) throw new ApiError(r.status, `${path}: ${r.status}`);
  return r.json() as Promise<T>;
}

export const api = {
  meta: (signal?: AbortSignal) => getJson<Meta>("/api/meta", signal),
  overview: (signal?: AbortSignal) => getJson<Overview>("/api/overview", signal),
  methodology: (signal?: AbortSignal) => getJson<Methodology>("/api/methodology", signal),
  articles: (query: string, signal?: AbortSignal) =>
    getJson<{ items: Article[]; offset: number; page_size: number }>(`/api/articles?${query}`, signal),
  article: (id: string | number, signal?: AbortSignal) => getJson<ArticleDetail>(`/api/articles/${id}`, signal),
  newCount: (since: string, signal?: AbortSignal) =>
    getJson<{ n: number }>(`/api/new?since=${encodeURIComponent(since)}`, signal),
};
