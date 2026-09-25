import { useCallback, useEffect, useState } from "react";

interface Result<T> {
  key: string;
  data: T | null;
  error: Error | null;
}

/** Tiny data-fetching hook: re-runs when `deps` change, exposes `reload`. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [tick, setTick] = useState(0);
  const key = JSON.stringify([...deps, tick]);
  const [result, setResult] = useState<Result<T>>({ key: "", data: null, error: null });

  useEffect(() => {
    let cancelled = false;
    fn()
      .then((data) => !cancelled && setResult({ key, data, error: null }))
      .catch((error: Error) => !cancelled && setResult((r) => ({ ...r, key, error })));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data: result.data, error: result.error, loading: result.key !== key, reload };
}
