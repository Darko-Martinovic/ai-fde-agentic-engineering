import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { errorMessage, useAction, usePoll, useRoute } from "./hooks";

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
    window.location.hash = "#/configuration";
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
  await waitFor(() => {
    expect(result.current).toEqual({ page: "configuration" });
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

  it("lets a load slower than the interval finish, rather than cutting it short", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let started = 0;
    const load = () => {
      started += 1;
      return new Promise<number>((resolve) => {
        setTimeout(() => {
          resolve(started);
        }, 2500);
      });
    };
    // Strict mode loads twice on mount, cutting the first load short, as the
    // dashboard does in development
    const { result } = renderHook(() => usePoll(load, 1000), {
      wrapper: StrictMode,
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2600);
    });
    expect(result.current.data).toBe(2);
    expect(started).toBe(2);
  });

  it("gives up on a load that never answers and loads afresh", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let started = 0;
    const load = () => {
      started += 1;
      return started === 1
        ? new Promise<number>(() => undefined)
        : Promise.resolve(started);
    };
    const { result } = renderHook(() => usePoll(load, 1000));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4100);
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
