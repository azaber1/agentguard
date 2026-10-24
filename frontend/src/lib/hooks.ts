"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";

export interface ApiState<T> {
  data: T | undefined;
  error: string | null;
  loading: boolean;
  reload: () => Promise<void>;
}

/**
 * Fetch `path` on mount (and whenever it changes). If `pollMs` returns a number for the
 * current data, the request repeats on that interval — used to follow running test runs.
 * A 401 sends the user back to the login page.
 */
export function useApi<T>(path: string | null, pollMs?: (data: T | undefined) => number | null): ApiState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(path !== null);
  const pollRef = useRef(pollMs);
  pollRef.current = pollMs;

  const load = useCallback(async () => {
    if (path === null) return;
    try {
      const result = await api<T>(path);
      setData(result);
      setError(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
        return;
      }
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    setLoading(path !== null);
    void load();
  }, [load, path]);

  useEffect(() => {
    const interval = pollRef.current?.(data);
    if (!interval) return;
    const id = window.setTimeout(() => void load(), interval);
    return () => window.clearTimeout(id);
  }, [data, load]);

  return { data, error, loading, reload: load };
}
