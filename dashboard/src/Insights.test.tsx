import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { InsightsPage } from "./Insights";
import { INSIGHTS, NO_INSIGHTS, mockFetch } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function stat(label: string) {
  const term = screen.getByText(label, { selector: "dt" });
  return term.parentElement?.textContent;
}

function bars(label: string) {
  return within(screen.getByRole("list", { name: label })).getAllByRole(
    "listitem",
  );
}

it("adds up the agent's work", async () => {
  mockFetch({ "GET /api/insights": INSIGHTS });
  render(<InsightsPage />);
  expect(await screen.findByText("50%")).toBeDefined();
  expect(stat("Straight through")).toContain("2 of 4 claims decided");
  expect(stat("Time per claim")).toBe("Time per claim7 sMedian; longest 10 s");
  expect(stat("Tool calls")).toBe("Tool calls51 refused by the backend");
  expect(stat("Waiting for a handler")).toContain("1 sign-off and 1 referral");
  expect(stat("Approved by the agent")).toContain("$1,570.00");
  expect(stat("Held for sign-off")).toContain("$1,150.00");
  expect(screen.getByText("Section 7, Emergency Medical")).toBeDefined();

  const table = screen.getByRole("table");
  const link = within(table).getByRole("link", { name: "CLM-1002" });
  expect(link.getAttribute("href")).toBe("#/claims/CLM-1002");
  expect(within(table).getAllByRole("row")).toHaveLength(3);
});

it("stacks each type's decisions to the claims of that type", async () => {
  mockFetch({ "GET /api/insights": INSIGHTS });
  render(<InsightsPage />);
  await screen.findByText("50%");
  const rows = bars("Decisions by claim type");
  const sums = rows.map((row) =>
    [...row.querySelectorAll(".bar__segment")].reduce(
      (total, segment) => total + Number(segment.textContent),
      0,
    ),
  );
  expect(sums).toEqual(
    INSIGHTS.by_type.map((mix) => mix.approve + mix.decline + mix.refer),
  );
  expect(
    rows.map((row) => row.querySelector(".bars__note")?.textContent),
  ).toEqual(sums.map(String));
  const medical = within(rows[1]);
  expect(medical.getByLabelText("Referred: 1")).toBeDefined();
  expect(medical.getByLabelText("Declined: 1").style.width).toBe("50%");
});

it("shows the refused calls against their tool", async () => {
  mockFetch({ "GET /api/insights": INSIGHTS });
  render(<InsightsPage />);
  await screen.findByText("50%");
  const pay = bars("Tool calls")[1];
  expect(within(pay).getByText("pay_claim")).toBeDefined();
  expect(within(pay).getByLabelText("Answered: 1")).toBeDefined();
  expect(within(pay).getByLabelText("Refused: 1")).toBeDefined();
});

it("says when the agent hasn't worked a claim", async () => {
  mockFetch({ "GET /api/insights": NO_INSIGHTS });
  render(<InsightsPage />);
  expect(
    await screen.findByText(/The agent hasn't worked a claim yet/),
  ).toBeDefined();
  expect(screen.queryByRole("table")).toBeNull();
});

it("shows an error and tries again", async () => {
  const fetchMock = mockFetch({
    "GET /api/insights": Response.json(
      { detail: "Database locked" },
      { status: 500 },
    ),
  });
  render(<InsightsPage />);
  expect(await screen.findByText("Database locked")).toBeDefined();
  mockFetch({ "GET /api/insights": INSIGHTS });
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("50%")).toBeDefined();
  expect(fetchMock).toHaveBeenCalled();
});
