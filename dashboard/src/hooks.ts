import { useEffect, useRef, useState } from "react";
import { api, type SettingsView } from "./api";
import { modelLabel } from "./configuration";
import { parseRoute, type Route } from "./paths";

export type Loader<T> = (signal: AbortSignal) => Promise<T>;

export interface Poll<T> {
  data: T | null;
  error: string | null;
  reload: () => void;
}

export function errorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "Something went wrong";
}

/** Run an action for a form or a button: busy while it runs, its error if it
 *  fails, and `onDone` afterwards either way, so the page shows what changed. */
export function useAction(onDone: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    action()
      .catch((reason: unknown) => {
        setError(errorMessage(reason));
      })
      .finally(() => {
        setBusy(false);
        onDone();
      });
  };
  return { busy, error, run };
}

/** How long a load that failed waits before it tries again, so data loaded
 *  once (an interval of null) comes back after the backend restarts. */
const RETRY_MS = 5000;
// How many intervals a load may take before the next tick gives up on it and
// loads afresh, so a request that never answers never stops the polling
const PATIENCE = 3;

/** Load data now, then again every `interval` ms while the page is visible,
 *  or, with no interval, every RETRY_MS until a load succeeds. A load slower
 *  than the interval finishes before the next starts, rather than being cut
 *  short by it. Pass a stable `load` (from useCallback); a new one loads
 *  afresh. */
export function usePoll<T>(load: Loader<T>, interval: number | null): Poll<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  // The load in flight, if any, and when it started; a load cut short by a
  // new one, as React's strict mode does on mount, never clears it
  const loading = useRef<AbortController | null>(null);
  const loadStarted = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    loading.current = controller;
    loadStarted.current = Date.now();
    load(controller.signal)
      .then(
        (value) => {
          setData(value);
          setError(null);
        },
        (reason: unknown) => {
          if (!controller.signal.aborted) setError(errorMessage(reason));
        },
      )
      .finally(() => {
        if (loading.current === controller) loading.current = null;
      });
    return () => {
      controller.abort();
    };
  }, [load, tick]);

  useEffect(() => {
    if (interval === null) return;
    const timer = setInterval(() => {
      const waited = Date.now() - loadStarted.current;
      const free = loading.current === null || waited > PATIENCE * interval;
      if (!document.hidden && free) setTick((t) => t + 1);
    }, interval);
    return () => {
      clearInterval(timer);
    };
  }, [interval]);

  useEffect(() => {
    if (interval !== null || error === null) return;
    const timer = setTimeout(() => {
      setTick((t) => t + 1);
    }, RETRY_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [interval, error, tick]);

  return {
    data,
    error,
    reload: () => {
      setTick((t) => t + 1);
    },
  };
}

/** The time now, in ms, kept current every `interval` ms, or held while
 *  `interval` is null. */
export function useNow(interval: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (interval === null) return;
    const timer = setInterval(() => {
      setNow(Date.now());
    }, interval);
    return () => {
      clearInterval(timer);
    };
  }, [interval]);
  return now;
}

export function useRoute(): Route {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => {
      setHash(window.location.hash);
    };
    window.addEventListener("hashchange", onChange);
    return () => {
      window.removeEventListener("hashchange", onChange);
    };
  }, []);
  return parseRoute(hash);
}

/** How to name a model: its label among the models allowed, or its name when
 *  it isn't one. The settings load once, however many are named. */
export function useModelLabels(): (model: string) => string {
  const settings = useSettings();
  return (model) => modelLabel(settings?.models_allowed ?? [], model);
}

/** The platform's settings and the models allowed, loaded once, or null
 *  until they load. */
export function useSettings(): SettingsView | null {
  return usePoll(api.getSettings, null).data;
}

/** A model's label among the models allowed, or its name. */
export function useModelLabel(model: string): string {
  return useModelLabels()(model);
}
