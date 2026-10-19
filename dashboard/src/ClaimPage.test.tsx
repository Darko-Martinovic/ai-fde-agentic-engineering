import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Customer, Decision, Policy, Step } from "./api";
import { ClaimPage } from "./ClaimPage";
import { IDLE, calledWith, claim, mockFetch, type Routes } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const POLICY: Policy = {
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  plan: {
    plan: "premium",
    name: "UnderCover Premium",
    trip_cancellation_max: 5000,
    trip_delay_waiting_hours: 6,
    trip_delay_max: 800,
    baggage_delay_waiting_hours: 12,
    baggage_delay_max: 300,
    baggage_max: 1500,
    per_item_limit: 300,
    passport_max: 250,
    emergency_medical_max: 100000,
    deductible: 50,
  },
  deductible_applies_to: ["baggage", "emergency_medical"],
  add_ons: [
    {
      add_on: "electronics_plus",
      name: "Electronics Plus",
      effect: "Raises the per-item limit for electronics.",
      electronics_per_item_limit: 1200,
    },
  ],
  purchased_on: "2026-04-22",
  sold_through: "Meridian Air checkout",
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100,
  },
  travelers: ["Maya Patel"],
  status: "active",
};

const CUSTOMER: Customer = {
  customer_id: "CUS-3001",
  name: "Maya Patel",
  email: "maya.patel@example.com",
  phone: "+1 201 555 0143",
  customer_since: "2023-04-11",
  previous_claims: [
    {
      claim_id: "CLM-0412",
      filed_on: "2024-08-19",
      incident_date: "2024-08-09",
      claim_type: "baggage_delay",
      summary: "Checked bag arrived 30 hours late in Lisbon",
      outcome: "approved",
      amount_paid: 140,
    },
  ],
};

const HANDLERS = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
  },
  { handler_id: "HND-02", name: "Marcus Oyelaran", role: "Claims Handler" },
];

function decision(overrides: Partial<Decision> = {}): Decision {
  return {
    decided_by: "agent",
    decision: "approve",
    payout: 1150,
    reasons: "The suitcase was lost by the carrier.",
    policy_section: "Section 5, Baggage and Personal Effects",
    decided_at: "2026-10-19T15:00:00Z",
    ...overrides,
  };
}

function routes(overrides: Routes = {}): Routes {
  return {
    "GET /api/claims/CLM-1001": claim(),
    "GET /api/claims/CLM-1001/steps": [],
    "GET /api/policies/POL-2001": POLICY,
    "GET /api/customers/CUS-3001": CUSTOMER,
    "GET /api/handlers": HANDLERS,
    "GET /api/agent": IDLE,
    ...overrides,
  };
}

it("shows the claim in full, with its policy and customer", async () => {
  mockFetch(routes());
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
    routes({
      "GET /api/claims/CLM-1001": claim({
        status: "decided",
        decisions: [decision({ payout: 420 })],
        payment: {
          amount: 420,
          authorized_by: "agent",
          paid_at: "2026-10-19T15:01:00Z",
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
    routes({
      "GET /api/claims/CLM-1001": claim({ status: "in_progress" }),
      "GET /api/claims/CLM-1001/steps": steps,
      "GET /api/agent": { running: true, mode: "claim", claim_id: "CLM-1001" },
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

it("signs off a large payout", async () => {
  const table = routes({
    "GET /api/claims/CLM-1001": claim({
      status: "awaiting_sign_off",
      decisions: [decision()],
    }),
    "POST /api/claims/CLM-1001/sign-off": claim(),
  });
  const fetchMock = mockFetch(table);
  render(<ClaimPage claimId="CLM-1001" />);
  const button = await screen.findByRole("button", {
    name: "Sign off $1,150.00",
  });
  await screen.findByRole("option", { name: /Marcus Oyelaran/ });
  fireEvent.change(screen.getByLabelText("Handler"), {
    target: { value: "HND-02" },
  });
  table["GET /api/claims/CLM-1001"] = claim({
    status: "decided",
    decisions: [decision()],
    payment: {
      amount: 1150,
      authorized_by: "HND-02",
      paid_at: "2026-10-19T15:05:00Z",
    },
  });
  fireEvent.click(button);
  expect(
    await screen.findByText(/authorized by Marcus Oyelaran/),
  ).toBeDefined();
  const signOff = fetchMock.mock.calls.find(
    ([, init]) => init?.method === "POST",
  );
  expect(signOff?.[1]?.body).toBe('{"handler_id":"HND-02"}');
});

it("lets a handler decide a referral", async () => {
  const table = routes({
    "GET /api/claims/CLM-1001": claim({
      status: "referred",
      decisions: [
        decision({
          decision: "refer",
          payout: 0,
          reasons: "The bill needs checking.",
        }),
      ],
    }),
    "POST /api/claims/CLM-1001/resolution": claim(),
  });
  const fetchMock = mockFetch(table);
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("The bill needs checking.")).toBeDefined();
  await screen.findByRole("option", { name: /Dana Whitfield/ });
  const submit = screen.getByRole("button", { name: "Record the decision" });
  expect(submit).toHaveProperty("disabled", true);

  fireEvent.change(screen.getByLabelText("Payout in US dollars"), {
    target: { value: "1350" },
  });
  fireEvent.change(screen.getByLabelText("Reasons"), {
    target: { value: "Covered emergency treatment." },
  });
  const approve = screen.getByRole("button", {
    name: "Approve and pay $1,350.00",
  });
  expect(approve).toHaveProperty("disabled", false);
  fireEvent.click(approve);
  await waitFor(() => {
    expect(calledWith(fetchMock, "POST /api/claims/CLM-1001/resolution")).toBe(
      true,
    );
  });
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
  expect(JSON.parse(call?.[1]?.body as string)).toEqual({
    handler_id: "HND-01",
    decision: "approve",
    payout: 1350,
    reasons: "Covered emergency treatment.",
  });

  fireEvent.click(screen.getByLabelText("Decline"));
  expect(screen.queryByLabelText("Payout in US dollars")).toBeNull();
  expect(
    screen.getByRole("button", { name: "Record the decision" }),
  ).toHaveProperty("disabled", false);
});

it("shows why a handler's action failed", async () => {
  mockFetch(
    routes({
      "GET /api/claims/CLM-1001": claim({
        status: "awaiting_sign_off",
        decisions: [decision()],
      }),
      "POST /api/claims/CLM-1001/sign-off": Response.json(
        { detail: "Handler HND-01 not found" },
        { status: 404 },
      ),
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  await screen.findByRole("option", { name: /Dana Whitfield/ });
  fireEvent.click(
    await screen.findByRole("button", { name: "Sign off $1,150.00" }),
  );
  expect(await screen.findByText("Handler HND-01 not found")).toBeDefined();
});

it("runs the agent on a waiting claim", async () => {
  const fetchMock = mockFetch(
    routes({
      "POST /api/agent/claims/CLM-1001": {
        running: true,
        mode: "claim",
        claim_id: null,
      },
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  fireEvent.click(await screen.findByRole("button", { name: "Run the agent" }));
  await waitFor(() => {
    expect(calledWith(fetchMock, "POST /api/agent/claims/CLM-1001")).toBe(true);
  });
});

it("returns a claim left in progress to the queue", async () => {
  const fetchMock = mockFetch(
    routes({
      "GET /api/claims/CLM-1001": claim({ status: "in_progress" }),
      "POST /api/agent/stop": IDLE,
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByText("Waiting for the agent's first step."),
  ).toBeDefined();
  fireEvent.click(
    await screen.findByRole("button", { name: "Return to the queue" }),
  );
  await waitFor(() => {
    expect(calledWith(fetchMock, "POST /api/agent/stop")).toBe(true);
  });
});

it("shows when the claim can't load", async () => {
  mockFetch({});
  render(<ClaimPage claimId="CLM-9999" />);
  expect(
    await screen.findByText("No route for GET /api/claims/CLM-9999"),
  ).toBeDefined();
});
