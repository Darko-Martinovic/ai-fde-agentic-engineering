import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  errorMessage,
  parseRoute,
  readTheme,
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

describe("parseRoute", () => {
  it("knows the four pages", () => {
    expect(parseRoute("")).toEqual({ page: "queue" });
    expect(parseRoute("#/")).toEqual({ page: "queue" });
    expect(parseRoute("#/instructions")).toEqual({ page: "instructions" });
    expect(parseRoute("#/insights")).toEqual({ page: "insights" });
    expect(parseRoute("#/claims/CLM-1001")).toEqual({
      page: "claim",
      claimId: "CLM-1001",
    });
    expect(parseRoute("#/claims/")).toEqual({ page: "queue" });
  });
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
