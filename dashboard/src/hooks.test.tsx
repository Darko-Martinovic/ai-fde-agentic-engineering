import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  errorMessage,
  readTheme,
  useAction,
  usePoll,
  useRoute,
  useTheme,
} from "./hooks";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  localStorage.clear();
  window.location.hash = "";
});

it("follows the hash", async () => {
  const { result } = renderHook(() => useRoute());
  act(() => {
    window.location.hash = "#/instructions";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
  await waitFor(() => {
    expect(result.current).toEqual({ page: "instructions" });
  });
});

describe("usePoll", () => {
  it("loads, then loads again on each interval", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let count = 0;
    const load = () => Promise.resolve(++count);
    const { result } = renderHook(() => usePoll(load, 1000));
    await waitFor(() => {
      expect(result.current.data).toBe(1);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(result.current.data).toBe(2);
  });

  it("reports errors and reloads on request", async () => {
    let fail = true;
    const load = () =>
      fail
        ? Promise.reject(new Error("Backend is down"))
        : Promise.resolve("ok");
    const { result } = renderHook(() => usePoll(load, null));
    await waitFor(() => {
      expect(result.current.error).toBe("Backend is down");
    });
    fail = false;
    act(() => {
      result.current.reload();
    });
    await waitFor(() => {
      expect(result.current.data).toBe("ok");
    });
    expect(result.current.error).toBeNull();
  });

  it("tries a failed load again until it succeeds, with no interval", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let fails = 2;
    const load = () =>
      fails-- > 0
        ? Promise.reject(new Error("Request failed (502)"))
        : Promise.resolve("ok");
    const { result } = renderHook(() => usePoll(load, null));
    await waitFor(() => {
      expect(result.current.error).toBe("Request failed (502)");
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(result.current.data).toBeNull();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(result.current.data).toBe("ok");
    expect(result.current.error).toBeNull();
  });

  it("describes errors that aren't Errors", () => {
    expect(errorMessage(new Error("x"))).toBe("x");
    expect(errorMessage("x")).toBe("Something went wrong");
  });
});

describe("useTheme", () => {
  it("applies and remembers the theme", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current[0]).toBe("system");
    act(() => {
      result.current[1]("dark");
    });
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(readTheme()).toBe("dark");
    act(() => {
      result.current[1]("system");
    });
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("falls back to the system theme when storage is blocked", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    });
    expect(readTheme()).toBe("system");
    const { result } = renderHook(() => useTheme());
    act(() => {
      result.current[1]("light");
    });
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});

describe("useAction", () => {
  it("is busy while the action runs, then refreshes", async () => {
    const onDone = vi.fn();
    const { result } = renderHook(() => useAction(onDone));
    let finish: () => void = () => undefined;
    act(() => {
      result.current.run(
        () =>
          new Promise<void>((resolve) => {
            finish = resolve;
          }),
      );
    });
    expect(result.current.busy).toBe(true);
    await act(async () => {
      finish();
      await Promise.resolve();
    });
    expect(result.current.busy).toBe(false);
    expect(result.current.error).toBeNull();
    expect(onDone).toHaveBeenCalledOnce();
  });

  it("shows why an action failed, and refreshes anyway", async () => {
    const onDone = vi.fn();
    const { result } = renderHook(() => useAction(onDone));
    act(() => {
      result.current.run(() => Promise.reject(new Error("Already running")));
    });
    await waitFor(() => {
      expect(result.current.error).toBe("Already running");
    });
    expect(onDone).toHaveBeenCalledOnce();
  });
});
