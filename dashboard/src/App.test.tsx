import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { INSIGHTS, MODELS, QUEUE, claim, mockFetch } from "./testing";

const ROUTES = {
  "GET /api/health": { status: "ok" },
  "GET /api/claims": QUEUE,
  "GET /api/dispatches/latest": null,
  "GET /api/claims/CLM-1001": claim(),
  "GET /api/instructions": "# UnderCover claim agent\n\nDecide claims.",
  "GET /api/models": MODELS,
  "GET /api/policy-wording": "# Policy Wording",
  "GET /api/insights": INSIGHTS,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
  localStorage.clear();
});

it("shows that the backend is up", async () => {
  mockFetch(ROUTES);
  render(<App />);
  expect(await screen.findByText("Backend: up")).toBeDefined();
});

it("shows that the backend is down", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  render(<App />);
  expect(await screen.findByText("Backend: down")).toBeDefined();
});

it("moves between pages", async () => {
  mockFetch(ROUTES);
  render(<App />);
  expect(await screen.findByText("CLM-1002")).toBeDefined();

  window.location.hash = "#/instructions";
  fireEvent(window, new HashChangeEvent("hashchange"));
  expect(
    await screen.findByRole("heading", { name: "UnderCover claim agent" }),
  ).toBeDefined();
  expect(
    screen
      .getByRole("link", { name: "Instructions" })
      .getAttribute("aria-current"),
  ).toBe("page");

  window.location.hash = "#/insights";
  fireEvent(window, new HashChangeEvent("hashchange"));
  expect(await screen.findByText("Straight through")).toBeDefined();
  expect(
    screen.getByRole("link", { name: "Insights" }).getAttribute("aria-current"),
  ).toBe("page");

  window.location.hash = "#/claims/CLM-1001";
  fireEvent(window, new HashChangeEvent("hashchange"));
  expect(
    await screen.findByText("Flight home canceled by the airline"),
  ).toBeDefined();
});

it("switches the theme", () => {
  mockFetch(ROUTES);
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "Dark" }));
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(
    screen.getByRole("button", { name: "Dark" }).getAttribute("aria-pressed"),
  ).toBe("true");
});
