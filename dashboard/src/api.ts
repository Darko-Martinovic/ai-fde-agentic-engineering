import type {
  AgentName,
  AgentState,
  Insights,
  ModelChoice,
  Run,
} from "./agentTypes";

import type {
  Claim,
  ClaimSummary,
  Customer,
  DocumentName,
  Handler,
  Policy,
  Section,
  Step,
} from "./claimTypes";

export type * from "./agentTypes";
export * from "./claimTypes";

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
  listClaims: (signal?: AbortSignal) =>
    getJson<ClaimSummary[]>("/api/claims", signal),
  getClaim: (id: string, signal?: AbortSignal) =>
    getJson<Claim>(`/api/claims/${id}`, signal),
  readSection: (document: DocumentName, num: number, signal?: AbortSignal) =>
    getJson<Section>(
      `/api/documents/${document}/sections/${String(num)}`,
      signal,
    ),
  listSteps: (id: string, signal?: AbortSignal) =>
    getJson<Step[]>(`/api/claims/${id}/steps`, signal),
  getPolicy: (id: string, signal?: AbortSignal) =>
    getJson<Policy>(`/api/policies/${id}`, signal),
  getCustomer: (id: string, signal?: AbortSignal) =>
    getJson<Customer>(`/api/customers/${id}`, signal),
  listHandlers: (signal?: AbortSignal) =>
    getJson<Handler[]>("/api/handlers", signal),
  getInstructions: (agent: AgentName, signal?: AbortSignal) =>
    getText(`/api/instructions/${agent}`, signal),
  getPolicyWording: (signal?: AbortSignal) =>
    getText("/api/policy-wording", signal),
  getAgent: (signal?: AbortSignal) => getJson<AgentState>("/api/agent", signal),
  getLatestRun: (signal?: AbortSignal) =>
    getJson<Run | null>("/api/runs/latest", signal),
  getInsights: (signal?: AbortSignal) =>
    getJson<Insights>("/api/insights", signal),
  health: (signal?: AbortSignal) =>
    getJson<{ status: string }>("/api/health", signal),
  listModels: (signal?: AbortSignal) =>
    getJson<ModelChoice[]>("/api/agent/models", signal),
  runClaim: (id: string, model: string) =>
    post<AgentState>(`/api/agent/claims/${id}`, { model }),
  runQueue: (cap: number, model: string) =>
    post<AgentState>("/api/agent/queue", { cap, model }),
  stopAgent: () => post<AgentState>("/api/agent/stop"),
  signOffClaim: (id: string, handlerId: string) =>
    post<Claim>(`/api/claims/${id}/sign-off`, { handler_id: handlerId }),
  decideAsHandler: (
    id: string,
    resolution: {
      handler_id: string;
      decision: "approve" | "decline";
      payout: number;
      reasons: string;
    },
  ) => post<Claim>(`/api/claims/${id}/handler-decision`, resolution),
};
