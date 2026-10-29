import { expect, type APIRequestContext } from "@playwright/test";
import { AS_THE_AGENT } from "./agent-key";

// The agent starts each claim in a dispatch or on its own; the tests start
// theirs on their own through the API.
export async function startClaim(request: APIRequestContext, claimId: string) {
  const response = await request.post(`/api/claims/${claimId}/start`, {
    data: { run_id: null, thread_id: `${claimId}-e2e` },
    headers: AS_THE_AGENT,
  });
  expect(response.ok()).toBe(true);
}
