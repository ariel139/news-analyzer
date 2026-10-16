// Outlet site icons, vendored once into src/assets/logos/<outlet id>.png so visitors never hit the outlets.
const logos = import.meta.glob<string>("../assets/logos/*.png", { eager: true, query: "?url", import: "default" });

const LOGO_BY_ID = new Map(
  Object.entries(logos).map(([file, url]) => [file.split("/").pop()!.replace(/\.png$/, ""), url]),
);

export const logoUrl = (outletId: string): string | undefined => LOGO_BY_ID.get(outletId);

export function OutletBadge({ id, name, size = 42 }: { id: string; name: string; size?: number }) {
  const url = logoUrl(id);
  if (url) return <img className="logo" src={url} alt="" width={size} height={size} loading="lazy" />;
  return <span className="monogram" aria-hidden="true">{name.slice(0, 1)}</span>;
}
