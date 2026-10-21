import { expect, test, type APIRequestContext } from "@playwright/test";
import { latestRun } from "./claim-starts";

// The queue agent's run is set up through the API, as the agent would record
// it, so no model is called.
async function send(
  request: APIRequestContext,
  method: "post" | "put",
  path: string,
  data: object,
) {
  const response = await request[method](path, { data });
  expect(response.ok()).toBe(true);
  return (await response.json()) as { run_id: number; status: string } | null;
}

async function finishAnyRun(request: APIRequestContext) {
  const latest = await latestRun(request);
  if (latest?.status === "running") {
    await send(request, "post", `/api/runs/${String(latest.run_id)}/finish`, {
      summary: "Finished by the end-to-end test.",
    });
  }
}

test("the queue page follows a run as it happens", async ({
  page,
  request,
}) => {
  await finishAnyRun(request);
  const run = await send(request, "post", "/api/runs", {
    mode: "queue",
    cap: 2,
    model: "e2e",
  });
  const runId = String(run?.run_id);
  await send(request, "put", `/api/runs/${runId}/todos`, {
    todos: [
      { content: "Work CLM-1012", status: "in_progress" },
      { content: "Work CLM-1013", status: "pending" },
    ],
  });
  await send(request, "post", "/api/claims/CLM-1012/start", {
    run_id: run?.run_id,
    thread_id: "CLM-1012-run",
  });
  await send(request, "post", "/api/claims/CLM-1012/steps", {
    thread_id: "CLM-1012-run",
    kind: "reply",
    text: "Reading the claim and the policy.",
  });

  await page.goto("/");
  const panel = page.getByRole("region", { name: "The latest run" });
  await expect(panel.getByText("Live")).toBeVisible();
  const todos = panel.getByRole("region", { name: "To-do list" });
  await expect(todos.getByText("Work CLM-1012")).toBeVisible();
  await expect(todos.getByText("In progress")).toBeVisible();
  const current = panel.getByRole("region", { name: "The claim being worked" });
  await expect(current.getByRole("link", { name: "CLM-1012" })).toBeVisible();
  await expect(
    current.getByText("Reading the claim and the policy."),
  ).toBeVisible();

  await send(request, "post", `/api/runs/${runId}/finish`, {
    summary: "CLM-1012 is still being worked; CLM-1013 waits for another run.",
  });
  await expect(
    panel.getByText(
      "CLM-1012 is still being worked; CLM-1013 waits for another run.",
    ),
  ).toBeVisible();
  await expect(panel.getByText(/^Finished at /)).toBeVisible();
});
