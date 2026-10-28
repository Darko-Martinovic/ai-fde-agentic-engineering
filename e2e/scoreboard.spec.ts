import { expect, test, type APIRequestContext } from "@playwright/test";
import { started } from "./stand-in";

const LUNA = "openrouter:openai/gpt-6-luna";

// The evaluation is played out through the API, as the agent's service and its
// claim agents record it, so no model is called.
async function send(request: APIRequestContext, path: string, data: object) {
  const response = await request.post(path, { data });
  expect(response.ok()).toBe(true);
  return (await response.json()) as { run_id: number };
}

/** The held-out set's tiny claims, as the agent might work them: CLM-1104
 *  approved for $250.00 and paid, CLM-1106 approved for $300.00 and paid,
 *  CLM-1110 referred, CLM-1112 approved for $1,200.00 and held, and CLM-1114
 *  not decided; each with a model call of $0.0125 and 40 seconds of work. */
const ANSWERS: [string, string | null, number][] = [
  ["CLM-1104", "approve", 250],
  ["CLM-1106", "approve", 300],
  ["CLM-1110", "refer", 0],
  ["CLM-1112", "approve", 1200],
  ["CLM-1114", null, 0],
];

async function workCopy(
  request: APIRequestContext,
  runId: number,
  [claimId, decision, payout]: [string, string | null, number],
) {
  const copyId = `${claimId}-E${String(runId)}`;
  const thread = `${copyId}-e2e`;
  await send(request, `/api/claims/${copyId}/start`, {
    run_id: runId,
    thread_id: thread,
  });
  if (decision) {
    await send(request, `/api/claims/${copyId}/decision`, {
      decision,
      payout,
      reasons: "Played out by the end-to-end test.",
      policy_section: "Section 5",
    });
  }
  if (decision === "approve" && payout <= 1000) {
    await send(request, `/api/claims/${copyId}/payment`, { amount: payout });
  }
  const spell = { thread_id: thread, run_id: runId, seconds: 40 };
  await send(request, `/api/claims/${copyId}/model-calls`, {
    ...spell,
    model: LUNA,
    input_tokens: 1000,
    output_tokens: 100,
    cost: 0.0125,
  });
  await send(request, `/api/claims/${copyId}/work-times`, spell);
}

test("the scoreboard starts an evaluation", async ({ page, request }) => {
  await page.goto("/#/scoreboard");
  const form = page.getByRole("form", { name: "Start an evaluation" });
  await form.getByLabel("Set").selectOption("held_out");
  await form.getByLabel("Claims").selectOption("tiny");
  await form.getByLabel("Claim agents at once").selectOption("5");
  await expect(form.getByLabel("Model")).toHaveCount(0);
  await form.getByRole("button", { name: "Start an evaluation" }).click();
  await expect
    .poll(() => started(request))
    .toContainEqual({
      evaluation: {
        evaluation_set: "held_out",
        tiny: true,
        agents: 5,
      },
    });
});

test("the scoreboard shows an evaluation scored from its records", async ({
  page,
  request,
}) => {
  const { run_id: runId } = await send(request, "/api/runs/evaluations", {
    evaluation_set: "held_out",
    tiny: true,
    agents: 5,
  });
  for (const answer of ANSWERS) await workCopy(request, runId, answer);
  await send(request, `/api/runs/${String(runId)}/finish`, { stopped: false });

  await page.goto("/#/scoreboard");
  const table = page.getByRole("table", { name: "Evaluations" });
  const row = table.getByRole("row").filter({ hasText: `#${String(runId)}` });
  for (const value of ["80%", "40%", "$620.00", "60%", "$0.0125", "40 s"]) {
    await expect(row.getByText(value, { exact: true })).toBeVisible();
  }

  await row.getByRole("link", { name: `#${String(runId)}` }).click();
  const copies = page.getByRole("table", { name: "The evaluation's claims" });
  const verdicts = [
    ["CLM-1104", "Right"],
    ["CLM-1106", "Miss"],
    ["CLM-1112", "Miss"],
    ["CLM-1114", "Miss"],
  ];
  for (const [claimId, verdict] of verdicts) {
    const copyRow = copies
      .getByRole("row")
      .filter({ hasText: `${claimId}-E${String(runId)}` });
    await expect(copyRow.getByText(verdict)).toBeVisible();
  }

  await copies
    .getByRole("link", { name: `CLM-1112-E${String(runId)}` })
    .click();
  await expect(page.getByText("A copy of CLM-1112 in")).toBeVisible();
  await expect(
    page.getByText(/Held for sign-off. In an evaluation/),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /Sign off/ })).toHaveCount(0);
});
