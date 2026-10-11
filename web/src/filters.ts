export interface Filters {
  outlets: string[];
  topic: string;
  leaning: string;
  type: string;
  analyzed: boolean;
  q: string;
}

export function parseFilters(p: URLSearchParams): Filters {
  return {
    outlets: [...new Set(p.getAll("outlet").filter(Boolean))],
    topic: p.get("topic") ?? "",
    leaning: p.get("leaning") ?? "",
    type: p.get("type") ?? "",
    analyzed: ["1", "true"].includes(p.get("analyzed") ?? ""),
    q: p.get("q") ?? "",
  };
}

/** Number shown on the filter button: everything in the popover (topic and search have their own UI). */
export function activeFilterCount(f: Filters): number {
  return f.outlets.length + [f.leaning, f.type, f.analyzed].filter(Boolean).length;
}
