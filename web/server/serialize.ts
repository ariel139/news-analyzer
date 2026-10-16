/** Row -> JSON for the API. Only whitelisted fields; article text is never selected, so never included. */
import type { OutletRegistry } from "./config.ts";
import type { Row } from "./db.ts";
import * as labels from "./labels.ts";

export function analysisDto(row: Row) {
  if (row.article_type == null) return null;
  const axes = labels.AXES.map((ax) => {
    const score = row[`${ax.key}_score`] as number | null;
    const conf = row[`${ax.key}_conf`] as string | null;
    return {
      ...ax,
      score,
      applicable: score !== null,
      confidence: conf,
      confidence_he: (conf && labels.CONFIDENCE[conf]) || "",
    };
  });
  const type = row.article_type as string;
  const topic = row.topic as string;
  const side = row.favored_side as string | null;
  return {
    article_type: type,
    article_type_he: labels.ARTICLE_TYPES[type] ?? type,
    topic,
    topic_he: labels.TOPICS[topic] ?? topic,
    favored_side: side,
    favored_side_he: side ? (labels.SIDES[side] ?? null) : null,
    axes,
    explanation: row.explanation as string,
    evidence: JSON.parse((row.evidence as string) || "[]") as string[],
    summary: row.summary as string,
    model: row.model as string,
    analyzed_at: row.analyzed_at as string,
  };
}

export function articleDto(row: Row, registry: OutletRegistry) {
  const status = row.status as string;
  return {
    id: row.id as number,
    outlet: row.outlet as string,
    outlet_name: registry.nameOf(row.outlet as string),
    title: row.title as string,
    url: row.url as string,
    author: row.author as string | null,
    published_at: row.published_at as string,
    status,
    status_he: labels.statusText(status, row.skip_reason as string | null),
    analysis: analysisDto(row),
  };
}

export type ArticleDto = ReturnType<typeof articleDto>;
