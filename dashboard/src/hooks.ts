import { useEffect, useState } from "react";
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
 *  fails, and `onDone` once it succeeds, so the page shows what changed. */
export function useAction(onDone: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    action()
      .then(onDone)
      .catch((reason: unknown) => {
        setError(errorMessage(reason));
      })
      .finally(() => {
        setBusy(false);
      });
  };
  return { busy, error, run };
}

/** Load data now, then again every `interval` ms while the page is visible.
 *  Pass a stable `load` (from useCallback); a new one loads afresh. */
export function usePoll<T>(load: Loader<T>, interval: number | null): Poll<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).then(
      (value) => {
        setData(value);
        setError(null);
      },
      (reason: unknown) => {
        if (!controller.signal.aborted) setError(errorMessage(reason));
      },
    );
    return () => {
      controller.abort();
    };
  }, [load, tick]);

  useEffect(() => {
    if (interval === null) return;
    const timer = setInterval(() => {
      if (!document.hidden) setTick((t) => t + 1);
    }, interval);
    return () => {
      clearInterval(timer);
    };
  }, [interval]);

  return {
    data,
    error,
    reload: () => {
      setTick((t) => t + 1);
    },
  };
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

export type Theme = "system" | "light" | "dark";
const THEME_KEY = "undercover-theme";

export function readTheme(): Theme {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    return saved === "light" || saved === "dark" ? saved : "system";
  } catch {
    return "system";
  }
}

export function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(readTheme);
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") delete root.dataset.theme;
    else root.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      // Private windows can refuse storage; the theme still applies.
    }
  }, [theme]);
  return [theme, setTheme];
}
