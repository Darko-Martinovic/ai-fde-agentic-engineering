import { vi } from "vitest";
import type { AgentState, Claim, ClaimSummary, Insights } from "./api";

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

export const IDLE: AgentState = { running: false, mode: null, claim_id: null };

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
    ...overrides,
  };
}

export const NO_INSIGHTS: Insights = {
  totals: {
    claims: 25,
    decided: 0,
    straight_through: 0,
    sign_offs: 0,
    referred: 0,
    waiting_for_handler: 0,
    tool_calls: 0,
    refused: 0,
    median_seconds: null,
    longest_seconds: null,
    claimed: 0,
    approved: 0,
    paid: 0,
    held: 0,
  },
  by_type: [],
  tools: [],
  sections: [],
  claims: [],
};

export const INSIGHTS: Insights = {
  totals: {
    claims: 25,
    decided: 4,
    straight_through: 2,
    sign_offs: 1,
    referred: 1,
    waiting_for_handler: 2,
    tool_calls: 5,
    refused: 1,
    median_seconds: 7,
    longest_seconds: 10,
    claimed: 6720,
    approved: 1570,
    paid: 420,
    held: 1150,
  },
  by_type: [
    { claim_type: "baggage", approve: 1, decline: 0, refer: 0 },
    { claim_type: "emergency_medical", approve: 0, decline: 1, refer: 1 },
    { claim_type: "trip_delay", approve: 1, decline: 0, refer: 0 },
  ],
  tools: [
    { tool: "decide_claim", calls: 2, refused: 0 },
    { tool: "pay_claim", calls: 2, refused: 1 },
    { tool: "get_claim", calls: 1, refused: 0 },
  ],
  sections: [
    { section: "Section 7, Emergency Medical", claims: 2 },
    { section: "Section 3, Trip Delay", claims: 1 },
  ],
  claims: [
    {
      claim_id: "CLM-1001",
      claim_type: "trip_delay",
      status: "decided",
      decision: "approve",
      started_at: "2026-10-19T10:00:00+00:00",
      finished_at: "2026-10-19T10:00:10+00:00",
      seconds: 10,
      tool_calls: 3,
      refused: 0,
    },
    {
      claim_id: "CLM-1002",
      claim_type: "baggage",
      status: "awaiting_sign_off",
      decision: "approve",
      started_at: "2026-10-19T10:00:12+00:00",
      finished_at: "2026-10-19T10:00:16+00:00",
      seconds: 4,
      tool_calls: 2,
      refused: 1,
    },
  ],
};
