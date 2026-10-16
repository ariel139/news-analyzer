import { useCallback, useEffect, useRef, useState } from "react";

export interface Fetched<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  reload: () => void;
}

/** Runs `load` whenever `key` changes and aborts the previous request. */
export function useFetch<T>(load: (signal: AbortSignal) => Promise<T>, key: string | number): Fetched<T> {
  const [state, setState] = useState<{ data: T | null; error: Error | null; loading: boolean }>({
    data: null, error: null, loading: true,
  });
  const [tick, setTick] = useState(0);
  const loadRef = useRef(load);
  loadRef.current = load;

  useEffect(() => {
    const ctl = new AbortController();
    setState((s) => ({ ...s, error: null, loading: true }));
    loadRef.current(ctl.signal).then(
      (data) => !ctl.signal.aborted && setState({ data, error: null, loading: false }),
      (error: Error) => !ctl.signal.aborted && setState({ data: null, error, loading: false }),
    );
    return () => ctl.abort();
  }, [key, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { ...state, reload };
}
