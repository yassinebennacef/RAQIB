import { useEffect, useRef, useState } from "react";

export interface ApiState<T> {
  data: T | undefined;
  error: string | undefined;
  loading: boolean;
}

/** Fetch on mount and whenever `key` changes; keeps the previous data while reloading. */
export function useApi<T>(fn: () => Promise<T>, key: string): ApiState<T> & { reload: () => void } {
  const [state, setState] = useState<ApiState<T>>({ data: undefined, error: undefined, loading: true });
  const [tick, setTick] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    let alive = true;
    Promise.resolve()
      .then(() => {
        if (alive) setState((s) => ({ ...s, loading: true }));
        return fnRef.current();
      })
      .then((data) => alive && setState({ data, error: undefined, loading: false }))
      .catch((e: unknown) =>
        alive && setState((s) => ({ ...s, error: e instanceof Error ? e.message : String(e), loading: false })),
      );
    return () => {
      alive = false;
    };
  }, [key, tick]);

  return { ...state, reload: () => setTick((t) => t + 1) };
}

export function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return v;
}
