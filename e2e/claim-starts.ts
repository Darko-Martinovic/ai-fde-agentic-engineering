import { expect, type APIRequestContext } from "@playwright/test";

// The agent starts each claim in a dispatch or on its own; the tests start
// theirs on their own through the API.
export async function startClaim(request: APIRequestContext, claimId: string) {
  const response = await request.post(`/api/claims/${claimId}/start`, {
    data: { run_id: null, thread_id: `${claimId}-e2e` },
  });
  expect(response.ok()).toBe(true);
}
