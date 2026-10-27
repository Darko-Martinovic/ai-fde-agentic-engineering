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

/** How long a load that failed waits before it tries again, so data loaded
 *  once (an interval of null) comes back after the backend restarts. */
const RETRY_MS = 5000;

/** Load data now, then again every `interval` ms while the page is visible,
 *  or, with no interval, every RETRY_MS until a load succeeds.
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

/** How to name a model: its label from models.toml, or its id when it is no
 *  longer listed. The models load once, however many are named. */
export function useModelLabels(): (spec: string) => string {
  const models = usePoll(api.listModels, null);
  return (spec) => models.data?.find((m) => m.spec === spec)?.label ?? spec;
}

/** A model's label from models.toml, or its id when it is no longer listed. */
export function useModelLabel(spec: string): string {
  return useModelLabels()(spec);
}
