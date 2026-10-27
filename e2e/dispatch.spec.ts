import { expect, test, type APIRequestContext } from "@playwright/test";
import { started } from "./stand-in";

// The dispatch is played out through the API, as the agent's service and its
// claim agents record it, so no model is called.
async function send(
  request: APIRequestContext,
  method: "post" | "put",
  path: string,
  data: object,
) {
  const response = await request[method](path, { data });
  expect(response.ok()).toBe(true);
  return (await response.json()) as { run_id: number };
}

async function work(
  request: APIRequestContext,
  runId: number,
  claimId: string,
  decision: object,
) {
  const thread = `${claimId}-dispatch`;
  await send(request, "post", `/api/claims/${claimId}/start`, {
    run_id: runId,
    thread_id: thread,
  });
  await send(request, "post", `/api/claims/${claimId}/model-calls`, {
    thread_id: thread,
    run_id: runId,
    model: "e2e",
    input_tokens: 1200,
    output_tokens: 300,
    cost: 0.0125,
    seconds: 1.5,
  });
  await send(request, "post", `/api/claims/${claimId}/decision`, decision);
  await send(request, "post", `/api/claims/${claimId}/work-times`, {
    thread_id: thread,
    run_id: runId,
    seconds: 40,
  });
}

test("the queue page follows a dispatch as it happens", async ({
  page,
  request,
}) => {
  const { run_id: runId } = await send(
    request,
    "post",
    "/api/runs/dispatches",
    {
      agents: 3,
      model: "e2e",
      reasoning_effort: "none",
    },
  );
  await send(request, "put", `/api/runs/${String(runId)}/claims`, {
    claim_ids: ["CLM-1013", "CLM-1014"],
  });

  await page.goto("/");
  const panel = page.getByRole("region", {
    name: `Dispatch #${String(runId)}`,
  });
  await expect(panel.getByText("Running")).toBeVisible();
  const claims = panel.getByRole("table", { name: "The dispatch's claims" });
  await expect(claims.getByText("Waiting")).toHaveCount(2);

  await work(request, runId, "CLM-1013", {
    decision: "decline",
    payout: 0,
    reasons: "The loss isn't covered.",
    policy_section: "Section 9, General exclusions",
  });
  await expect(claims.getByText("Decided")).toBeVisible();
  await send(request, "post", "/api/claims/CLM-1014/start", {
    run_id: runId,
    thread_id: "CLM-1014-dispatch",
  });
  await expect(claims.getByText("In progress")).toBeVisible();

  await send(request, "post", `/api/runs/${String(runId)}/finish`, {
    stopped: false,
  });
  await expect(panel.getByText("Finished")).toBeVisible();
  await expect(panel.getByText("$0.0125").first()).toBeVisible();
  const summary = panel.getByRole("region", { name: "Summary" });
  await expect(
    summary.getByText("0 approved, 1 declined and 0 referred."),
  ).toBeVisible();
  await expect(
    summary.getByText("Left for the next dispatch: CLM-1014"),
  ).toBeVisible();
});

test("the queue page starts a dispatch and stops one", async ({
  page,
  request,
}) => {
  await page.goto("/");
  const form = page.getByRole("form", { name: "Start a dispatch" });
  await form.getByLabel("Claim agents at once").selectOption("7");
  await expect(form.getByLabel("Model")).toHaveValue(
    "openrouter:openai/gpt-6-luna",
  );
  await form.getByRole("button", { name: "Start a dispatch" }).click();
  await expect
    .poll(() => started(request))
    .toContainEqual({
      dispatch: { agents: 7, model: "openrouter:openai/gpt-6-luna" },
    });

  const { run_id: runId } = await send(
    request,
    "post",
    "/api/runs/dispatches",
    {
      agents: 7,
      model: "e2e",
      reasoning_effort: "none",
    },
  );
  await form.getByRole("button", { name: "Stop" }).click();
  await expect.poll(() => started(request)).toContainEqual({ stop: {} });
  await send(request, "post", `/api/runs/${String(runId)}/finish`, {
    stopped: true,
  });
  await expect(page.getByText("Stopped")).toBeVisible();
});
