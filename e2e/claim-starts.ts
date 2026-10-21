import { expect, type APIRequestContext } from "@playwright/test";

// The agent starts each claim in a run; the tests do the same through the API,
// in a run named for them that can take the whole queue.
const QUEUE_SIZE = 25;
async function aRun(request: APIRequestContext): Promise<number> {
  const latest = (await (await request.get("/api/runs/latest")).json()) as {
    run_id: number;
    status: string;
  } | null;
  if (latest?.status === "running") return latest.run_id;
  const run = await request.post("/api/runs", {
    data: { mode: "queue", cap: QUEUE_SIZE, model: "e2e" },
  });
  return ((await run.json()) as { run_id: number }).run_id;
}

export async function startClaim(request: APIRequestContext, claimId: string) {
  const response = await request.post(`/api/claims/${claimId}/start`, {
    data: { run_id: await aRun(request), thread_id: `${claimId}-e2e` },
  });
  expect(response.ok()).toBe(true);
}
