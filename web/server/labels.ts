/** Hebrew display labels. The DB and the LLM use the English keys. */

export const ARTICLE_TYPES: Record<string, string> = { news: "ידיעה חדשותית", analysis: "פרשנות", opinion: "דעה" };

export const TOPICS: Record<string, string> = {
  security: "ביטחון", diplomacy: "מדיני", politics: "פוליטיקה", economy: "כלכלה",
  law: "משפט", religion_state: "דת ומדינה", society: "חברה", health: "בריאות",
  education: "חינוך", culture: "תרבות", sports: "ספורט", other: "אחר",
};

// Topics offered in the section bar. Sports/culture/other are mostly skipped by the analyzer.
export const NAV_TOPICS = Object.keys(TOPICS).filter((k) => !["sports", "culture", "other"].includes(k));

export const CONFIDENCE: Record<string, string> = { low: "נמוכה", medium: "בינונית", high: "גבוהה" };

export const SIDES: Record<string, string> = { left: "שמאל", right: "ימין", none: "ללא נטייה" };

export interface AxisDef {
  key: string;
  title: string;
  low: string;
  high: string;
  min: number;
  max: number;
}

// key = DB column prefix; low/high = what the two ends of the scale mean
export const AXES: AxisDef[] = [
  { key: "overall", title: "סיכום שמאל–ימין", low: "שמאל", high: "ימין", min: -2, max: 2 },
  { key: "security", title: "ביטחון ומדיניות חוץ", low: "יוני", high: "ניצי", min: -2, max: 2 },
  { key: "religion", title: "דת ומדינה", low: "ליברלי־חילוני", high: "דתי־מסורתי", min: -2, max: 2 },
  { key: "economy", title: "כלכלה", low: "מעורבות מדינה", high: "שוק חופשי", min: -2, max: 2 },
  { key: "tone", title: "טון", low: "ניטרלי", high: "טעון רגשית", min: 0, max: 4 },
];

export const LEANINGS: Record<string, string> = {
  "-2": "שמאל", "-1": "שמאל־מרכז", "0": "מרכז / ללא נטייה", "1": "ימין־מרכז", "2": "ימין",
  na: "לא רלוונטי פוליטית",
};

const STATUS: Record<string, string> = {
  pending: "ממתין לניתוח",
  paywalled: "תוכן בתשלום – לא נותח",
  failed: "הניתוח נכשל",
  skipped: "לא נותח",
};

const SKIP_REASONS: Record<string, string> = {
  category: "קטגוריה שאינה מנותחת (ספורט, מזג אוויר, בידור)",
  robots: "האתר אינו מתיר גישה אוטומטית לעמוד",
  short_text: "אין מספיק טקסט זמין לניתוח (ייתכן תוכן בתשלום או וידאו)",
  fetch_error: "לא ניתן היה לטעון את הכתבה",
  invalid_output: "המודל לא החזיר תשובה תקינה",
};

export function statusText(status: string, reason: string | null): string {
  const base = STATUS[status] ?? status;
  return reason && reason in SKIP_REASONS ? `${base}: ${SKIP_REASONS[reason]}` : base;
}
