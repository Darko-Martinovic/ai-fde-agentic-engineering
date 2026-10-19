export type ClaimStatus =
  "waiting" | "in_progress" | "awaiting_sign_off" | "referred" | "decided";

export type DecisionKind = "approve" | "decline" | "refer";

export interface ClaimSummary {
  claim_id: string;
  claim_type: string;
  customer_name: string;
  amount_claimed: number;
  submitted_on: string;
  status: ClaimStatus;
  decision: DecisionKind | null;
  payout: number | null;
  paid: number | null;
}

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Decision {
  decided_by: string;
  decision: DecisionKind;
  payout: number;
  reasons: string;
  policy_section: string | null;
  decided_at: string;
}

export interface Payment {
  amount: number;
  authorized_by: string;
  paid_at: string;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  items: Item[];
  amount_claimed: number;
  documents: ClaimDocument[];
  status: ClaimStatus;
  decisions: Decision[];
  payment: Payment | null;
}

export interface Plan {
  plan: string;
  name: string;
  trip_cancellation_max: number;
  trip_delay_waiting_hours: number;
  trip_delay_max: number;
  baggage_delay_waiting_hours: number;
  baggage_delay_max: number;
  baggage_max: number;
  per_item_limit: number;
  passport_max: number;
  emergency_medical_max: number;
  deductible: number;
}

export interface AddOn {
  add_on: string;
  name: string;
  effect: string;
  electronics_per_item_limit: number | null;
}

export interface Policy {
  policy_id: string;
  customer_id: string;
  plan: Plan;
  deductible_applies_to: string[];
  add_ons: AddOn[];
  purchased_on: string;
  sold_through: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  status: string;
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  incident_date: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface Customer {
  customer_id: string;
  name: string;
  email: string;
  phone: string;
  customer_since: string;
  previous_claims: PreviousClaim[];
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
}

export type StepKind = "tool_call" | "tool_result" | "reply";

export interface Step {
  thread_id: string;
  kind: StepKind;
  text: string;
  recorded_at: string;
}

export interface AgentState {
  running: boolean;
  mode: "claim" | "queue" | null;
  claim_id: string | null;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      detail?: unknown;
    };
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${String(response.status)})`;
    throw new ApiError(response.status, detail);
  }
  return response;
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return (await (await send(path, { signal })).json()) as T;
}

async function getText(path: string, signal?: AbortSignal): Promise<string> {
  return (await send(path, { signal })).text();
}

async function post<T>(path: string, body: object = {}): Promise<T> {
  const response = await send(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return (await response.json()) as T;
}

export const api = {
  claims: (signal?: AbortSignal) =>
    getJson<ClaimSummary[]>("/api/claims", signal),
  claim: (id: string, signal?: AbortSignal) =>
    getJson<Claim>(`/api/claims/${id}`, signal),
  steps: (id: string, signal?: AbortSignal) =>
    getJson<Step[]>(`/api/claims/${id}/steps`, signal),
  policy: (id: string, signal?: AbortSignal) =>
    getJson<Policy>(`/api/policies/${id}`, signal),
  customer: (id: string, signal?: AbortSignal) =>
    getJson<Customer>(`/api/customers/${id}`, signal),
  handlers: (signal?: AbortSignal) =>
    getJson<Handler[]>("/api/handlers", signal),
  instructions: (signal?: AbortSignal) => getText("/api/instructions", signal),
  policyWording: (signal?: AbortSignal) =>
    getText("/api/policy-wording", signal),
  agent: (signal?: AbortSignal) => getJson<AgentState>("/api/agent", signal),
  health: (signal?: AbortSignal) =>
    getJson<{ status: string }>("/api/health", signal),
  runClaim: (id: string) => post<AgentState>(`/api/agent/claims/${id}`),
  runQueue: () => post<AgentState>("/api/agent/queue"),
  stopAgent: () => post<AgentState>("/api/agent/stop"),
  signOff: (id: string, handlerId: string) =>
    post<Claim>(`/api/claims/${id}/sign-off`, { handler_id: handlerId }),
  resolve: (
    id: string,
    resolution: {
      handler_id: string;
      decision: "approve" | "decline";
      payout: number;
      reasons: string;
    },
  ) => post<Claim>(`/api/claims/${id}/resolution`, resolution),
};
