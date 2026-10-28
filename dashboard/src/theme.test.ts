import { afterEach, expect, it, vi } from "vitest";
import { applyTheme, readTheme, saveTheme } from "./theme";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

it("shows and remembers the theme", () => {
  expect(readTheme()).toBe("system");
  saveTheme("dark");
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(readTheme()).toBe("dark");
  saveTheme("system");
  expect(document.documentElement.dataset.theme).toBeUndefined();
  expect(readTheme()).toBe("system");
});

it("shows the theme kept before the page renders", () => {
  localStorage.setItem("undercover-theme", "light");
  applyTheme(readTheme());
  expect(document.documentElement.dataset.theme).toBe("light");
});

it("falls back to the computer's theme when storage is blocked", () => {
  vi.stubGlobal("localStorage", {
    getItem: () => {
      throw new Error("blocked");
    },
    setItem: () => {
      throw new Error("blocked");
    },
  });
  expect(readTheme()).toBe("system");
  saveTheme("light");
  expect(document.documentElement.dataset.theme).toBe("light");
});
