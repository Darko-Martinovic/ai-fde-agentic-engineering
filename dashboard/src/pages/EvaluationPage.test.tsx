import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { EvaluationPage } from "./EvaluationPage";
import { CONFIGURATION, evaluation, mockFetch } from "../testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function rowOf(claimId: string) {
  const table = screen.getByRole("table", { name: "The evaluation's claims" });
  const link = within(table).getByRole("link", { name: claimId });
  const row = link.closest("tr");
  if (!row) throw new Error(`No row for ${claimId}`);
  return within(row);
}

it("shows each copy beside the handler's decision, the misses marked", async () => {
  mockFetch({
    "GET /api/evaluations/4": evaluation(),
    "GET /api/configuration": CONFIGURATION,
  });
  render(<EvaluationPage runId={4} />);
  expect(
    await screen.findByRole("region", { name: "Evaluation #4" }),
  ).toBeDefined();
  expect(screen.getByText("Held-out set, 3 tiny")).toBeDefined();
  expect(screen.getByText("80%")).toBeDefined();
  const right = rowOf("CLM-1104-E4");
  expect(right.getByText("Right")).toBeDefined();
  expect(right.getByText("CLM-1104")).toBeDefined();
  expect(
    right.getByText("The bag was delayed 30 hours, and the receipts cover it."),
  ).toBeDefined();
  const over = rowOf("CLM-1106-E4");
  expect(over.getByText("Miss")).toBeDefined();
  expect(over.getByText("$300.00")).toBeDefined();
  expect(over.getByText("$250.00")).toBeDefined();
  const undecided = rowOf("CLM-1114-E4");
  expect(undecided.getByText("No decision")).toBeDefined();
  expect(undecided.getByText("Declined")).toBeDefined();
  expect(
    screen.getByRole("link", { name: "CLM-1104-E4" }).getAttribute("href"),
  ).toBe("#/claims/CLM-1104-E4");
  expect(
    screen
      .getByRole("link", { name: "Back to the scoreboard" })
      .getAttribute("href"),
  ).toBe("#/scoreboard");
});

it("shows when the evaluation can't load", async () => {
  mockFetch({ "GET /api/configuration": CONFIGURATION });
  render(<EvaluationPage runId={9} />);
  expect(
    await screen.findByText("No route for GET /api/evaluations/9"),
  ).toBeDefined();
});
