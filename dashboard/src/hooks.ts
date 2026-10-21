import { useEffect, useState } from "react";
import { api } from "./api";
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

const MODEL_KEY = "undercover-model";

function readModel(): string {
  try {
    return localStorage.getItem(MODEL_KEY) ?? "";
  } catch {
    return "";
  }
}

/** The models the agent may run on, and the one picked: the default (MODEL_NAME)
 *  until someone picks another, which the queue and the claim pages share. */
export function useModelChoice() {
  const models = usePoll(api.listModels, null);
  const [picked, setPicked] = useState(readModel);
  const list = models.data ?? [];
  const allowed = list.some((m) => m.spec === picked);
  const fallback = list.find((m) => m.default)?.spec ?? "";
  const pick = (spec: string) => {
    setPicked(spec);
    try {
      localStorage.setItem(MODEL_KEY, spec);
    } catch {
      // Private windows can refuse storage; the pick holds on this page.
    }
  };
  return {
    models: list,
    model: allowed ? picked : fallback,
    error: models.error,
    pick,
  };
}
