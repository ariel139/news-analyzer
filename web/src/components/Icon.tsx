import type { ReactNode } from "react";

const common = { fill: "none", stroke: "currentColor", strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

const ICONS: Record<string, { sw: number; body: ReactNode; join?: boolean }> = {
  info: { sw: 2, body: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></> },
  search: { sw: 2, body: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></> },
  filter: { sw: 2, body: <path d="M4 6h16M7 12h10M10 18h4" /> },
  close: { sw: 2.2, body: <path d="M6 6l12 12M18 6 6 18" /> },
  x: { sw: 2.4, body: <path d="M7 7l10 10M17 7 7 17" /> },
  home: { sw: 2, body: <path d="M4 11.5 12 5l8 6.5V19a1 1 0 0 1-1 1h-4v-5h-6v5H5a1 1 0 0 1-1-1z" /> },
  chart: { sw: 2, body: <path d="M4 19h16M7 15v-3M12 15V7M17 15v-6" /> },
  chevDown: { sw: 2.2, body: <path d="m6 9 6 6 6-6" /> },
  chevUp: { sw: 2.2, body: <path d="m6 15 6-6 6 6" /> },
  link: { sw: 2, body: <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /> },
  external: { sw: 2, body: <path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /> },
  sun: { sw: 2, body: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></> },
  moon: { sw: 2, body: <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" /> },
};

export function Icon({ name, className = "" }: { name: keyof typeof ICONS | string; className?: string }) {
  const def = ICONS[name];
  return (
    <svg className={`icon ${className}`.trim()} viewBox="0 0 24 24" strokeWidth={def.sw} aria-hidden="true" {...common}>
      {def.body}
    </svg>
  );
}

export function BrandMark() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M4 15h16M6 9h12" />
      <circle cx="14" cy="15" r="2.4" fill="currentColor" stroke="none" />
    </svg>
  );
}
