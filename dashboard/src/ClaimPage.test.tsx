import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Step } from "./api";
import { ClaimPage } from "./ClaimPage";
import {
  IDLE,
  calledWith,
  claim,
  claimRoutes,
  decision,
  mockFetch,
} from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("shows the claim in full, with its policy and customer", async () => {
  mockFetch(claimRoutes());
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByRole("heading", {
      name: "Flight home canceled by the airline",
    }),
  ).toBeDefined();
  expect(
    screen.getByText("My flight home from Rome was canceled."),
  ).toBeDefined();
  expect(screen.getByText("Airport hotel")).toBeDefined();
  expect(screen.getByText("Documents (1)")).toBeDefined();
  expect(screen.getByText("Total paid: $245.00")).toBeDefined();
  expect(await screen.findByText("UnderCover Premium")).toBeDefined();
  expect(screen.getByText("Electronics Plus")).toBeDefined();
  expect(screen.getByText("$100,000.00")).toBeDefined();
  expect(
    await screen.findByText("Maya Patel", { selector: ".customer__name" }),
  ).toBeDefined();
  expect(
    screen.getByText("Checked bag arrived 30 hours late in Lisbon"),
  ).toBeDefined();
  expect(screen.getByText("No decision yet.")).toBeDefined();
  expect(
    screen.getByText("The agent hasn't worked on this claim yet."),
  ).toBeDefined();
});

it("shows a decision, its section and the payment", async () => {
  mockFetch(
    claimRoutes({
      "GET /api/claims/CLM-1001": claim({
        status: "decided",
        decisions: [decision({ payout: 420 })],
        payment: {
          amount: 420,
          authorized_by: "agent",
          paid_at: "2026-10-19T15:01:00Z",
          signed_off_at: null,
        },
      }),
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("Approved")).toBeDefined();
  expect(
    screen.getByText("Section 5, Baggage and Personal Effects"),
  ).toBeDefined();
  expect(
    screen.getByText(
      /Paid \$420\.00 on Oct 19, 2026, authorized by UnderCover Agent/,
    ),
  ).toBeDefined();
});

it("shows the agent's steps live while it works", async () => {
  const steps: Step[] = [
    {
      thread_id: "t",
      kind: "tool_call",
      text: 'get_claim {"claim_id": "CLM-1001"}',
      recorded_at: "2026-10-19T15:00:00Z",
    },
    {
      thread_id: "t",
      kind: "tool_result",
      text: '{"claim_id":"CLM-1001"}',
      recorded_at: "2026-10-19T15:00:01Z",
    },
    {
      thread_id: "t",
      kind: "tool_result",
      text: "Refused (409): A payout over $1,000.00 waits for a handler's sign-off",
      recorded_at: "2026-10-19T15:00:02Z",
    },
    {
      thread_id: "t",
      kind: "reply",
      text: "Approved; the payment waits for sign-off.",
      recorded_at: "2026-10-19T15:00:03Z",
    },
  ];
  mockFetch(
    claimRoutes({
      "GET /api/claims/CLM-1001": claim({ status: "in_progress" }),
      "GET /api/claims/CLM-1001/steps": steps,
      "GET /api/agent": {
        ...IDLE,
        running: true,
        mode: "claim",
        claim_id: "CLM-1001",
      },
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("get_claim")).toBeDefined();
  expect(screen.getByText("Live")).toBeDefined();
  expect(screen.getByText('{"claim_id": "CLM-1001"}')).toBeDefined();
  expect(document.querySelector("pre")?.textContent).toBe(
    '{\n  "claim_id": "CLM-1001"\n}',
  );
  expect(
    screen.getByText(
      "Refused (409): A payout over $1,000.00 waits for a handler's sign-off",
    ),
  ).toBeDefined();
  expect(
    screen.getByText("Approved; the payment waits for sign-off."),
  ).toBeDefined();
  fireEvent.click(await screen.findByRole("button", { name: "Stop" }));
  await waitFor(() => {
    expect(screen.getByText("No route for POST /api/agent/stop")).toBeDefined();
  });
});

it("runs the agent on a waiting claim", async () => {
  const fetchMock = mockFetch(
    claimRoutes({
      "POST /api/agent/claims/CLM-1001": {
        ...IDLE,
        running: true,
        mode: "claim",
        claim_id: null,
      },
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  const run = await screen.findByRole("button", { name: "Run the agent" });
  await waitFor(() => {
    expect(calledWith(fetchMock, "GET /api/agent/models")).toBe(true);
  });
  fireEvent.click(run);
  await waitFor(() => {
    expect(calledWith(fetchMock, "POST /api/agent/claims/CLM-1001")).toBe(true);
  });
  const sent = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
  expect(JSON.parse(sent?.[1]?.body as string)).toEqual({
    model: "openrouter:deepseek/deepseek-v4.1-flash",
  });
});

it("leaves a claim a stopped run left in progress for the next run", async () => {
  mockFetch(
    claimRoutes({
      "GET /api/claims/CLM-1001": claim({ status: "in_progress" }),
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByText("Waiting for the agent's first step."),
  ).toBeDefined();
  expect(screen.queryByRole("button", { name: "Run the agent" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
});

it("shows when the claim can't load", async () => {
  mockFetch({});
  render(<ClaimPage claimId="CLM-9999" />);
  expect(
    await screen.findByText("No route for GET /api/claims/CLM-9999"),
  ).toBeDefined();
});
