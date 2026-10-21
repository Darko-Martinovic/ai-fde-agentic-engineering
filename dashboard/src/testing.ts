import { vi } from "vitest";
import type {
  AgentState,
  Claim,
  ClaimSummary,
  Customer,
  Decision,
  Insights,
  ModelChoice,
  Policy,
} from "./api";

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

export const MODELS: ModelChoice[] = [
  {
    spec: "openrouter:deepseek/deepseek-v4.1-flash",
    label: "DeepSeek V4.1 Flash",
    default: true,
  },
  {
    spec: "anthropic:claude-haiku-5-5",
    label: "Claude Haiku 5.5",
    default: false,
  },
];

export const IDLE: AgentState = {
  model: null,
  running: false,
  mode: null,
  claim_id: null,
};

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

export const HANDLERS = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
  },
  { handler_id: "HND-02", name: "Marcus Oyelaran", role: "Claims Handler" },
];

export function decision(overrides: Partial<Decision> = {}): Decision {
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

export function claimRoutes(overrides: Routes = {}): Routes {
  return {
    "GET /api/claims/CLM-1001": claim(),
    "GET /api/claims/CLM-1001/steps": [],
    "GET /api/policies/POL-2001": POLICY,
    "GET /api/customers/CUS-3001": CUSTOMER,
    "GET /api/handlers": HANDLERS,
    "GET /api/agent": IDLE,
    "GET /api/agent/models": MODELS,
    ...overrides,
  };
}
