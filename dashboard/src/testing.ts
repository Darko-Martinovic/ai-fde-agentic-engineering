import { render } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { vi } from "vitest";
import type {
  Claim,
  ClaimSummary,
  Customer,
  Decision,
  Handler,
  Policy,
} from "./api";
import { HandlerContext } from "./handler";
import { MODELS } from "./agentFixtures";

export * from "./agentFixtures";

/** Routes keyed by "METHOD /path": a value is sent as JSON (a string as text),
 *  a Response as it is, and a missing route answers 404. */
export type Routes = Record<string, unknown>;

function urlOf(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  return input instanceof URL ? input.href : input.url;
}

export function mockFetch(routes: Routes) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${urlOf(input)}`;
    const route = routes[key];
    if (route === undefined) {
      return Promise.resolve(
        Response.json({ detail: `No route for ${key}` }, { status: 404 }),
      );
    }
    if (route instanceof Response) return Promise.resolve(route.clone());
    if (typeof route === "string") return Promise.resolve(new Response(route));
    return Promise.resolve(Response.json(route));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function calledWith(
  fetchMock: ReturnType<typeof mockFetch>,
  key: string,
): boolean {
  return fetchMock.mock.calls.some(
    ([input, init]) => `${init?.method ?? "GET"} ${urlOf(input)}` === key,
  );
}

export function summary(overrides: Partial<ClaimSummary> = {}): ClaimSummary {
  return {
    claim_id: "CLM-1001",
    claim_type: "trip_delay",
    customer_name: "Maya Patel",
    amount_claimed: 420,
    submitted_on: "2026-06-24",
    status: "waiting",
    decision: null,
    payout: null,
    paid: null,
    ...overrides,
  };
}

export const QUEUE: ClaimSummary[] = [
  summary(),
  summary({
    claim_id: "CLM-1002",
    claim_type: "baggage",
    customer_name: "Tom Becker",
    amount_claimed: 1150,
    submitted_on: "2026-07-20",
    status: "awaiting_sign_off",
    decision: "approve",
    payout: 1150,
  }),
  summary({
    claim_id: "CLM-1003",
    claim_type: "emergency_medical",
    customer_name: "Aiko Tanaka",
    amount_claimed: 3800,
    submitted_on: "2026-07-06",
    status: "decided",
    decision: "decline",
    payout: 0,
  }),
  summary({
    claim_id: "CLM-1005",
    claim_type: "passport",
    customer_name: "Oliver Grant",
    amount_claimed: 243,
    submitted_on: "2026-07-14",
    status: "decided",
    decision: "approve",
    payout: 243,
    paid: 243,
  }),
];

export function claim(overrides: Partial<Claim> = {}): Claim {
  return {
    claim_id: "CLM-1001",
    policy_id: "POL-2001",
    customer_id: "CUS-3001",
    claim_type: "trip_delay",
    submitted_on: "2026-06-24",
    incident_date: "2026-06-18",
    incident_location: "Rome, Italy",
    summary: "Flight home canceled by the airline",
    story: "My flight home from Rome was canceled.",
    items: [
      { description: "Airport hotel", category: "accommodation", amount: 245 },
      { description: "Taxis", category: "transport", amount: 80 },
    ],
    amount_claimed: 325,
    documents: [
      {
        name: "Hotel receipt",
        type: "receipt",
        content: "Total paid: $245.00",
      },
    ],
    status: "waiting",
    decisions: [],
    payment: null,
    evaluation_id: null,
    copy_of: null,
    ...overrides,
  };
}

// A claim page's records, for the claim page and its decision forms
export const POLICY: Policy = {
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

export const CUSTOMER: Customer = {
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

export const DANA: Handler = {
  handler_id: "HND-01",
  name: "Dana Whitfield",
  role: "Senior Claims Handler",
  email: "dana.whitfield@undercover.example",
  can_approve_over_limit: true,
};

export const MARCUS: Handler = {
  handler_id: "HND-02",
  name: "Marcus Oyelaran",
  role: "Claims Handler",
  email: "marcus.oyelaran@undercover.example",
  can_approve_over_limit: false,
};

export const HANDLERS = [DANA, MARCUS];

/** Render a page as the signed-in handler, Dana Whitfield unless named. */
export function renderAs(ui: ReactNode, handler: Handler = DANA) {
  return render(createElement(HandlerContext.Provider, { value: handler }, ui));
}

export function decision(overrides: Partial<Decision> = {}): Decision {
  return {
    decided_by: "agent",
    decision: "approve",
    payout: 1150,
    reasons: "The suitcase was lost by the carrier.",
    policy_section: "Section 5, Baggage and Personal Effects",
    decided_at: "2026-10-19T15:00:00Z",
    review: null,
    reviewed_by: null,
    reviewed_at: null,
    review_note: null,
    ...overrides,
  };
}

export function claimRoutes(overrides: Routes = {}): Routes {
  return {
    "GET /api/claims/CLM-1001": claim(),
    "GET /api/claims/CLM-1001/steps": [],
    "GET /api/policies/POL-2001": POLICY,
    "GET /api/customers/CUS-3001": CUSTOMER,
    "GET /api/handlers": HANDLERS,
    "GET /api/me": DANA,
    "GET /api/models": MODELS,
    ...overrides,
  };
}
