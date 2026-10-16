import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import type { Meta, Overview } from "./types";

interface DataValue {
  meta: Meta;
  overview: Overview | null;
  refreshOverview: () => Promise<void>;
}

const Ctx = createContext<DataValue | null>(null);

export function useData(): DataValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useData outside DataProvider");
  return v;
}

/** Loads the labels and outlet list once, and the sidebar numbers (which can be refreshed). */
export function DataProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [failed, setFailed] = useState(false);
  const [overview, setOverview] = useState<Overview | null>(null);

  const refreshOverview = useCallback(async () => {
    try {
      setOverview(await api.overview());
    } catch {
      // The DB may not exist yet; the rail simply shows no counts.
    }
  }, []);

  useEffect(() => {
    const ctl = new AbortController();
    api.meta(ctl.signal).then(setMeta, () => !ctl.signal.aborted && setFailed(true));
    void refreshOverview();
    return () => ctl.abort();
  }, [refreshOverview]);

  if (failed) {
    return (
      <p className="empty" role="alert" style={{ margin: 24 }}>
        <strong>לא ניתן לטעון את האתר</strong>נסו לרענן את הדף.
      </p>
    );
  }
  if (!meta) return <p className="visually-hidden">טוען…</p>;
  return <Ctx.Provider value={{ meta, overview, refreshOverview }}>{children}</Ctx.Provider>;
}
