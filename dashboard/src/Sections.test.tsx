import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Step } from "./api";
import { SectionsPanel } from "./Sections";
import { mockFetch } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function read(document: string, number: number, title: string): Step {
  return {
    thread_id: "CLM-1001-a",
    kind: "section",
    text: JSON.stringify({
      document,
      document_title:
        document === "manual" ? "Claims manual" : "Policy wording",
      number,
      title,
    }),
    recorded_at: "2026-10-21T10:00:00Z",
  };
}

const STEPS: Step[] = [
  read("manual", 10, "Meals without receipts"),
  read("wording", 3, "Trip Delay"),
  read("manual", 10, "Meals without receipts"),
];

it("lists each section read once, in the order first read", () => {
  render(<SectionsPanel steps={STEPS} />);
  expect(
    screen.getAllByRole("listitem").map((item) => item.textContent),
  ).toEqual([
    "Claims manual 10. Meals without receipts",
    "Policy wording 3. Trip Delay",
  ]);
});

it("opens a section's text in place", async () => {
  const fetchMock = mockFetch({
    "GET /api/documents/manual/sections/10": {
      document: "manual",
      number: 10,
      title: "Meals without receipts",
      text: "## 10. Meals without receipts\n\nA flat $35 per traveler.",
    },
  });
  render(<SectionsPanel steps={STEPS} />);
  expect(fetchMock).not.toHaveBeenCalled();
  const details = screen
    .getByText("Claims manual 10. Meals without receipts")
    .closest("details");
  if (!details) throw new Error("no details");
  details.open = true;
  fireEvent(details, new Event("toggle"));
  expect(await screen.findByText("A flat $35 per traveler.")).toBeDefined();
});

it("says when a section can't load", async () => {
  mockFetch({});
  render(<SectionsPanel steps={STEPS} />);
  const details = screen
    .getByText("Policy wording 3. Trip Delay")
    .closest("details");
  if (!details) throw new Error("no details");
  details.open = true;
  fireEvent(details, new Event("toggle"));
  expect(await screen.findByRole("alert")).toBeDefined();
});

it("shows nothing before the agent reads a section", () => {
  const { container } = render(<SectionsPanel steps={[]} />);
  expect(container.textContent).toBe("");
});
