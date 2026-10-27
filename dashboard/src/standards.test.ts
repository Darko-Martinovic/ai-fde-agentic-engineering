// @vitest-environment node
// Checks that hold the dashboard and the TypeScript config to
// docs/CODE_STANDARDS.md. The Python parts have the same in tests/test_standards.py.
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const SOURCE = "dashboard/src/";
const CONFIGS = [
  "dashboard/vite.config.ts",
  "playwright.config.ts",
  "settings/settings.config.ts",
];

function product(): string[] {
  return readdirSync(ROOT + SOURCE)
    .filter((name) => /\.tsx?$/.test(name) && !/\.test\.tsx?$/.test(name))
    .filter((name) => name !== "testing.ts")
    .map((name) => SOURCE + name);
}

function offending(files: string[], pattern: RegExp, allowed: string[] = []) {
  return files
    .filter((file) => !allowed.includes(file))
    .flatMap((file) =>
      readFileSync(ROOT + file, "utf-8")
        .split("\n")
        .filter((line) => pattern.test(line))
        .map((line) => `${file}: ${line.trim()}`),
    );
}

describe("the dashboard keeps to the code standards", () => {
  it("writes no host, port or URL (standard 22)", () => {
    const address = /https?:\/\/|localhost|127\.0\.0\.1/;
    expect(offending([...product(), ...CONFIGS], address)).toEqual([]);
  });

  it("calls the backend only through api.ts (standards 7, 15)", () => {
    const api = [`${SOURCE}api.ts`];
    expect(offending(product(), /fetch\(/, api)).toEqual([]);
    expect(offending(product(), /["'`]\/api\//, api)).toEqual([]);
  });

  it("builds page links only in paths.ts (standard 19)", () => {
    expect(offending(product(), /["'`]#\//, [`${SOURCE}paths.ts`])).toEqual([]);
  });
});
