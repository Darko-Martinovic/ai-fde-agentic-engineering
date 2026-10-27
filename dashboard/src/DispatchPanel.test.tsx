import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { DispatchPanel } from "./DispatchPanel";
import { MODELS, mockFetch, run, runClaim } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function panel() {
  return screen.getByRole("region", { name: "Dispatch #7" });
}

it("says when there has been no dispatch", async () => {
  mockFetch({ "GET /api/dispatches/latest": null, "GET /api/models": MODELS });
  render(<DispatchPanel />);
  expect(await screen.findByText("No dispatch yet.")).toBeDefined();
});

it("follows a running dispatch, claim by claim", async () => {
  mockFetch({ "GET /api/dispatches/latest": run(), "GET /api/models": MODELS });
  render(<DispatchPanel />);
  expect(await screen.findByText("Running")).toBeDefined();
  expect(await within(panel()).findByText("GPT-6 Luna")).toBeDefined();
  expect(within(panel()).getByText("1 of 2")).toBeDefined();
  expect(within(panel()).getByText("$0.0204")).toBeDefined();
  const claims = within(panel()).getByRole("table", {
    name: "The dispatch's claims",
  });
  const link = within(claims).getByRole("link", { name: "CLM-1002" });
  expect(link.getAttribute("href")).toBe("#/claims/CLM-1002");
  expect(within(claims).getByText("In progress")).toBeDefined();
  expect(within(claims).getByText("None yet")).toBeDefined();
  expect(within(claims).getByText("$420.00")).toBeDefined();
  expect(within(claims).getByText("12 s")).toBeDefined();
  expect(screen.queryByRole("region", { name: "Summary" })).toBeNull();
});

it("shows a finished dispatch's time and what it left", async () => {
  const finished = run({
    status: "finished",
    finished_at: "2026-10-27T10:02:41Z",
    seconds: 161,
    claims: [runClaim()],
    summary: {
      approved: 3,
      declined: 1,
      referred: 1,
      waiting_for_sign_off: [{ claim_id: "CLM-1008", payout: 2240 }],
      left_for_handler: [],
      unfinished: ["CLM-1012"],
    },
  });
  mockFetch({
    "GET /api/dispatches/latest": finished,
    "GET /api/models": MODELS,
  });
  render(<DispatchPanel />);
  expect(await screen.findByText("Finished")).toBeDefined();
  expect(within(panel()).getByText("2 min 41 s")).toBeDefined();
  const summary = screen.getByRole("region", { name: "Summary" });
  expect(
    within(summary).getByText("3 approved, 1 declined and 1 referred."),
  ).toBeDefined();
  expect(
    within(summary).getByText("Waiting for sign-off: CLM-1008 $2,240.00"),
  ).toBeDefined();
  expect(
    within(summary).getByText("Left for the next dispatch: CLM-1012"),
  ).toBeDefined();
  expect(within(summary).queryByText(/Left for a handler/)).toBeNull();
});

it("shows a stopped dispatch", async () => {
  mockFetch({
    "GET /api/dispatches/latest": run({ status: "stopped", claims: [] }),
    "GET /api/models": MODELS,
  });
  render(<DispatchPanel />);
  expect(await screen.findByText("Stopped")).toBeDefined();
  expect(screen.getByText("No claims to work.")).toBeDefined();
});

it("shows when the dispatch can't load", async () => {
  mockFetch({});
  render(<DispatchPanel />);
  expect(
    await screen.findByText("No route for GET /api/dispatches/latest"),
  ).toBeDefined();
});
