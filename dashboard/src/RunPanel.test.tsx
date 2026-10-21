import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { ClaimSummary, Step } from "./api";
import { RunPanel } from "./RunPanel";
import { MODELS, QUEUE, mockFetch, run, summary } from "./testing";

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-21T10:02:00Z"));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

// CLM-1001 is done, CLM-1002 is being worked, and three more wait for the cap
const CLAIMS: ClaimSummary[] = [
  ...QUEUE.map((claim): ClaimSummary => {
    if (claim.claim_id === "CLM-1001") return { ...claim, status: "decided" };
    if (claim.claim_id === "CLM-1002")
      return { ...claim, status: "in_progress" };
    return claim;
  }),
  ...["CLM-1006", "CLM-1007", "CLM-1008"].map((id) =>
    summary({ claim_id: id }),
  ),
];

function step(thread: string, text: string): Step {
  return {
    thread_id: thread,
    kind: "reply",
    text,
    recorded_at: "2026-10-21T10:01:30Z",
  };
}

function fact(name: string) {
  const term = screen.getByText(name, { selector: "dt" });
  return term.nextElementSibling?.textContent;
}

it("shows a live run: its model, progress, time left, usage and to-do list", async () => {
  mockFetch({
    "GET /api/runs/latest": run(),
    "GET /api/agent/models": MODELS,
    "GET /api/claims/CLM-1002/steps": [
      step("CLM-1002-first", "The first attempt."),
      step("CLM-1002-again", "Reading the claim again."),
    ],
  });
  render(<RunPanel claims={CLAIMS} />);
  expect(await screen.findByText("Live")).toBeDefined();
  expect(await screen.findByText("Claude Haiku 5.5")).toBeDefined();
  expect(fact("Claims")).toBe("1 of 5");
  expect(fact("Time")).toBe("2 min, about 8 min left");
  expect(fact("Model calls")).toBe("16");
  expect(fact("Tokens in / out")).toBe("72,240 / 4,316");
  expect(fact("Cost")).toBe("$0.0094");
  expect(
    screen.getByRole("progressbar", { name: "Claims worked" }),
  ).toHaveProperty("value", 1);

  const todos = within(screen.getByRole("region", { name: "To-do list" }));
  expect(todos.getByText("Work CLM-1001")).toBeDefined();
  expect(todos.getByText("Done")).toBeDefined();
  expect(todos.getByText("In progress")).toBeDefined();

  const current = within(
    screen.getByRole("region", { name: "The claim being worked" }),
  );
  expect(current.getByRole("link", { name: "CLM-1002" })).toBeDefined();
  expect(await current.findByText("Reading the claim again.")).toBeDefined();
  expect(current.queryByText("The first attempt.")).toBeNull();
});

it("shows a finished run's summary and how long it took", async () => {
  mockFetch({
    "GET /api/runs/latest": run({
      status: "finished",
      finished_at: "2026-10-21T10:00:39Z",
      summary: "Approved CLM-1001; CLM-1002 waits for a sign-off.",
    }),
    "GET /api/agent/models": MODELS,
  });
  render(<RunPanel claims={CLAIMS} />);
  expect(
    await screen.findByText(
      "Approved CLM-1001; CLM-1002 waits for a sign-off.",
    ),
  ).toBeDefined();
  expect(screen.getByText(/^Finished at /)).toBeDefined();
  expect(fact("Time")).toBe("39 s");
  expect(
    screen.queryByRole("region", { name: "The claim being worked" }),
  ).toBeNull();
  const started = within(
    screen.getByRole("list", { name: "Claims in this run" }),
  );
  expect(started.getByRole("link", { name: "CLM-1001" })).toBeDefined();
});

it("marks a stopped run, and names a model no longer listed by its id", async () => {
  mockFetch({
    "GET /api/runs/latest": run({
      status: "stopped",
      finished_at: "2026-10-21T10:01:00Z",
      model: "ollama:retired",
      todos: [{ content: "Work CLM-1001", status: "left_for_handler" }],
    }),
    "GET /api/agent/models": MODELS,
  });
  render(<RunPanel claims={CLAIMS} />);
  expect(await screen.findByText(/^Stopped at /)).toBeDefined();
  expect(screen.getByText("Left for a handler")).toBeDefined();
  expect(screen.getByText("ollama:retired")).toBeDefined();
});

it("leaves the to-do list out of a run on named claims", async () => {
  mockFetch({
    "GET /api/runs/latest": run({ mode: "claim", cap: 1, todos: [] }),
    "GET /api/agent/models": MODELS,
    "GET /api/claims/CLM-1002/steps": [],
  });
  render(<RunPanel claims={CLAIMS} />);
  expect(
    await screen.findByRole("heading", { name: "The latest claim run" }),
  ).toBeDefined();
  expect(screen.queryByRole("region", { name: "To-do list" })).toBeNull();
  expect(
    await screen.findByText("Waiting for the agent's first step."),
  ).toBeDefined();
});

it("shows nothing before the first run", async () => {
  const fetchMock = mockFetch({
    "GET /api/runs/latest": null,
    "GET /api/agent/models": MODELS,
  });
  const { container } = render(<RunPanel claims={CLAIMS} />);
  await vi.waitFor(() => {
    expect(fetchMock).toHaveBeenCalled();
  });
  expect(container.textContent).toBe("");
});

it("says when the run can't be loaded", async () => {
  mockFetch({ "GET /api/agent/models": MODELS });
  render(<RunPanel claims={CLAIMS} />);
  expect(
    await screen.findByText("No route for GET /api/runs/latest"),
  ).toBeDefined();
});
