import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { QueuePage } from "./Queue";
import { QUEUE, mockFetch } from "../testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

function rows() {
  return screen
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[0]?.textContent);
}

it("shows the counts, the money and the claims", async () => {
  mockFetch({
    "GET /api/claims": QUEUE,
    "GET /api/dispatches/latest": null,
  });
  render(<QueuePage />);
  expect(await screen.findByText("CLM-1001")).toBeDefined();
  const decided = screen.getByRole("button", { name: /Decided/ });
  expect(decided.textContent).toBe("2Decided");
  expect(screen.getByText("$1,150.00", { selector: "dd" })).toBeDefined();
  expect(screen.getByText("$243.00", { selector: "dd" })).toBeDefined();
  expect(rows()).toEqual(["CLM-1001", "CLM-1002", "CLM-1003", "CLM-1005"]);
  expect(screen.getByText("Declined")).toBeDefined();
  expect(
    screen.getByText("Awaiting sign-off", { selector: ".badge" }),
  ).toBeDefined();
  expect(screen.getByText("4 of 4 claims")).toBeDefined();
});

it("filters by tile, search and type, and sorts", async () => {
  mockFetch({
    "GET /api/claims": QUEUE,
    "GET /api/dispatches/latest": null,
  });
  render(<QueuePage />);
  await screen.findByText("CLM-1001");

  fireEvent.click(screen.getByRole("button", { name: /Decided/ }));
  expect(rows()).toEqual(["CLM-1003", "CLM-1005"]);
  fireEvent.click(screen.getByRole("button", { name: /Decided/ }));
  expect(rows()).toHaveLength(4);

  fireEvent.change(screen.getByLabelText("Search"), {
    target: { value: "tanaka" },
  });
  expect(rows()).toEqual(["CLM-1003"]);
  fireEvent.change(screen.getByLabelText("Search"), { target: { value: "" } });

  fireEvent.change(screen.getByLabelText("Type"), {
    target: { value: "passport" },
  });
  expect(rows()).toEqual(["CLM-1005"]);
  fireEvent.change(screen.getByLabelText("Type"), { target: { value: "all" } });

  fireEvent.click(screen.getByRole("button", { name: "Claimed" }));
  expect(rows()).toEqual(["CLM-1005", "CLM-1001", "CLM-1002", "CLM-1003"]);
  fireEvent.click(screen.getByRole("button", { name: "Claimed" }));
  expect(rows()[0]).toBe("CLM-1003");
  expect(
    screen
      .getByRole("columnheader", { name: "Claimed" })
      .getAttribute("aria-sort"),
  ).toBe("descending");
});

it("says when nothing matches", async () => {
  mockFetch({
    "GET /api/claims": QUEUE,
    "GET /api/dispatches/latest": null,
  });
  render(<QueuePage />);
  await screen.findByText("CLM-1001");
  fireEvent.change(screen.getByLabelText("Search"), {
    target: { value: "nobody" },
  });
  expect(screen.getByText("No claims match these filters.")).toBeDefined();
});

it("shows an error and tries again", async () => {
  const routes: Record<string, unknown> = {
    "GET /api/claims": Response.json(
      { detail: "Database locked" },
      { status: 500 },
    ),
    "GET /api/dispatches/latest": null,
  };
  mockFetch(routes);
  render(<QueuePage />);
  expect(await screen.findByText("Database locked")).toBeDefined();
  routes["GET /api/claims"] = QUEUE;
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("CLM-1001")).toBeDefined();
});
