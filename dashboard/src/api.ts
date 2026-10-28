import type {
  Evaluation,
  EvaluationSet,
  Insights,
  Run,
  Started,
  Stopping,
} from "./agentTypes";

import type {
  Claim,
  ClaimSummary,
  Customer,
  DocumentName,
  Handler,
  HandlerName,
  Policy,
  Section,
  Step,
} from "./claimTypes";

import { accessToken } from "./auth";

import type {
  Configuration,
  SettingsIn,
  SettingsView,
  VersionDetails,
} from "./improvementTypes";

export type * from "./agentTypes";
export * from "./claimTypes";
export type * from "./improvementTypes";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/** Send a request, with the signed-in handler's access token, and throw the
 *  backend's refusal. */
async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = await accessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { ...init, headers });
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

async function sendJson<T>(
  method: "POST" | "PUT",
  path: string,
  body: object,
): Promise<T> {
  const response = await send(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return (await response.json()) as T;
}

function post<T>(path: string, body: object = {}): Promise<T> {
  return sendJson<T>("POST", path, body);
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
    getJson<HandlerName[]>("/api/handlers", signal),
  getSignedInHandler: (signal?: AbortSignal) =>
    getJson<Handler>("/api/me", signal),
  getPolicyWording: (signal?: AbortSignal) =>
    getText("/api/policy-wording", signal),
  getLatestDispatch: (signal?: AbortSignal) =>
    getJson<Run | null>("/api/dispatches/latest", signal),
  getInsights: (signal?: AbortSignal) =>
    getJson<Insights>("/api/insights", signal),
  health: (signal?: AbortSignal) =>
    getJson<{ status: string }>("/api/health", signal),
  getConfiguration: (signal?: AbortSignal) =>
    getJson<Configuration>("/api/configuration", signal),
  getVersionDetails: (number: number, signal?: AbortSignal) =>
    getJson<VersionDetails>(
      `/api/configuration/versions/${String(number)}`,
      signal,
    ),
  getSettings: (signal?: AbortSignal) =>
    getJson<SettingsView>("/api/settings", signal),
  changeSettings: (settings: SettingsIn) =>
    sendJson<SettingsView>("PUT", "/api/settings", settings),
  startDispatch: (agents: number) =>
    post<Started>("/api/dispatches", { agents }),
  stopRun: () => post<Stopping>("/api/runs/stop-request"),
  startEvaluation: (start: {
    evaluation_set: EvaluationSet;
    tiny: boolean;
    agents: number;
  }) => post<Started>("/api/evaluations", start),
  listEvaluations: (signal?: AbortSignal) =>
    getJson<Evaluation[]>("/api/evaluations", signal),
  getEvaluation: (runId: number, signal?: AbortSignal) =>
    getJson<Evaluation>(`/api/evaluations/${String(runId)}`, signal),
  reviewPayout: (id: string, review: { approved: boolean; note: string }) =>
    post<Claim>(`/api/claims/${id}/review`, review),
  decideAsHandler: (
    id: string,
    resolution: {
      decision: "approve" | "decline";
      payout: number;
      reasons: string;
    },
  ) => post<Claim>(`/api/claims/${id}/handler-decision`, resolution),
};
