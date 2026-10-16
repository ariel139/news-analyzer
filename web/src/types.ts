export interface AxisDef {
  key: string;
  title: string;
  low: string;
  high: string;
  min: number;
  max: number;
}

export type Confidence = "low" | "medium" | "high";

export interface Axis extends AxisDef {
  score: number | null;
  applicable: boolean;
  confidence: Confidence | null;
  confidence_he: string;
}

export interface Analysis {
  article_type: string;
  article_type_he: string;
  topic: string;
  topic_he: string;
  favored_side: string | null;
  favored_side_he: string | null;
  axes: Axis[];
  explanation: string;
  evidence: string[];
  summary: string;
  model: string;
  analyzed_at: string;
}

export interface Article {
  id: number;
  outlet: string;
  outlet_name: string;
  title: string;
  url: string;
  author: string | null;
  published_at: string;
  status: string;
  status_he: string;
  analysis: Analysis | null;
}

export type AuthorProfile =
  | { author: string; n: number; shown: false; min: number }
  | { author: string; n: number; shown: true; avg: number; text: string; caveat: string };

export interface ArticleDetail extends Article {
  author_profile: AuthorProfile | null;
}

export interface Meta {
  outlets: Record<string, string>;
  topics: Record<string, string>;
  nav_topics: string[];
  article_types: Record<string, string>;
  leanings: Record<string, string>;
  axes: AxisDef[];
  timezone: string;
}

export interface Overview {
  outlets: Record<string, number>;
  topics: Record<string, number>;
  last_collected: string | null;
  stats: {
    total: number;
    analyzed: number;
    outlets: number;
    pending: number;
    paywalled: number;
    last_24h: number;
    coverage: number;
  };
  breakdown: {
    leaning: Record<string, number>;
    not_political: number;
    types: Record<string, number>;
  };
}

export interface Methodology {
  model: string;
  min_author: number;
  retention: number;
  outlets: { id: string; name: string; enabled: boolean }[];
}
