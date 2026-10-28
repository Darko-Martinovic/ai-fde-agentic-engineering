import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { ClaimWork } from "../api";
import { latestRun, layout } from "../runs";
import { Timeline } from "./Timeline";

afterEach(cleanup);

function work(
  claimId: string,
  start: string,
  end: string,
  decision: ClaimWork["decision"] = "approve",
): ClaimWork {
  return {
    claim_id: claimId,
    claim_type: "baggage",
    status: "decided",
    decision,
    started_at: `2026-10-19T${start}Z`,
    finished_at: `2026-10-19T${end}Z`,
    seconds:
      (Date.parse(`2026-10-19T${end}Z`) - Date.parse(`2026-10-19T${start}Z`)) /
      1000,
    tool_calls: 4,
    refused: 0,
  };
}

const EARLIER = work("CLM-1001", "09:00:00", "09:00:30");
const RUN = [
  work("CLM-1002", "10:00:00", "10:00:20"),
  work("CLM-1003", "10:00:25", "10:01:00", "decline"),
  work("CLM-1004", "10:01:05", "10:01:40", null),
];

it("picks the claims of the latest run", () => {
  expect(latestRun([EARLIER, ...RUN]).map((c) => c.claim_id)).toEqual([
    "CLM-1002",
    "CLM-1003",
    "CLM-1004",
  ]);
  expect(latestRun([EARLIER, ...RUN].toReversed())).toHaveLength(3);
  expect(latestRun([])).toEqual([]);
});

it("keeps claims within five minutes of each other in one run", () => {
  const near = work("CLM-1001", "09:55:00", "09:55:30");
  expect(latestRun([near, ...RUN])).toHaveLength(4);
});

it("places each claim between the run's first and last steps", () => {
  const { start, end, bars } = layout(RUN);
  expect(end - start).toBe(100);
  expect(bars.map((b) => [b.left, b.width])).toEqual([
    [0, 20],
    [25, 35],
    [65, 35],
  ]);
});

it("draws the latest run", () => {
  render(<Timeline claims={[EARLIER, ...RUN]} />);
  expect(screen.getByText(/^3 claims in 1 min 40 s, from/)).toBeDefined();
  const rows = within(screen.getByRole("list", { name: "The latest run" }));
  expect(rows.getAllByRole("listitem")).toHaveLength(3);
  expect(
    rows.getByRole("link", { name: "CLM-1003" }).getAttribute("href"),
  ).toBe("#/claims/CLM-1003");
  const declined = rows.getByLabelText("Declined in 35 s");
  expect(declined.style.left).toBe("25%");
  expect(declined.style.width).toBe("35%");
  expect(rows.getByLabelText("No decision in 35 s")).toBeDefined();
});

it("draws nothing before a run", () => {
  const { container } = render(<Timeline claims={[]} />);
  expect(container.textContent).toBe("");
});
