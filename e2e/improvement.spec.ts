import { expect, test, type APIRequestContext } from "@playwright/test";
import { SIGNED_IN } from "./signed-in";
import { started } from "./stand-in";

// A round played out through the API, as the agent's service and the improver
// record it, so no model is called: its first evaluations, finished with their
// copies undecided, then a change for a handler to review.
const DANA = "HND-01";
const CHANGE = {
  instructions:
    "# UnderCover claim agent\n\nRefer a claim the manual flags for review.",
  model: "openai/gpt-6-luna",
  reasoning_effort: "medium",
  reason: "Fewer wrong approvals of claims the manual flags.",
};
const SETS = ["evaluation", "held_out", "held_out"];

async function send(request: APIRequestContext, path: string, data = {}) {
  const response = await request.post(path, { data });
  expect(response.ok(), await response.text()).toBe(true);
  return (await response.json()) as Record<string, unknown>;
}

async function evaluations(request: APIRequestContext, roundId: number) {
  for (const evaluationSet of SETS) {
    const run = await send(
      request,
      `/api/runs/rounds/${String(roundId)}/evaluations`,
      { evaluation_set: evaluationSet },
    );
    await send(request, `/api/runs/${String(run.run_id)}/finish`, {
      stopped: false,
    });
  }
}

async function review(
  request: APIRequestContext,
  roundId: number,
  proposalId: number,
  approved: boolean,
) {
  const path = `/api/rounds/${String(roundId)}/proposals/${String(proposalId)}/review`;
  await send(request, path, { handler_id: DANA, approved, note: "" });
}

test.describe.configure({ mode: "serial" });

// The round the first test starts, which the second carries on
let roundId = 0;

// Whatever happens, the round ends, so later tests find none open
test.afterAll(async ({ request }) => {
  if (roundId === 0) return;
  await request.post(`/api/rounds/${String(roundId)}/finish`, {
    data: { stopped: true, reason: "The end-to-end test is done with it" },
  });
});

test("a change waits with its diff, and Dana's approval reaches the service", async ({
  page,
  request,
}) => {
  const round = await send(request, "/api/rounds", {
    handler_id: DANA,
    thread_id: "improver-e2e",
  });
  roundId = Number(round.round_id);
  await evaluations(request, roundId);
  const proposal = await send(
    request,
    `/api/rounds/${String(roundId)}/proposals/changes`,
    CHANGE,
  );

  await page.goto("/#/improvement");
  await expect(page.getByRole("status")).toHaveText(
    "A change waiting for approval",
  );
  const panel = page.getByRole("region", {
    name: "A change waits for your review",
  });
  await expect(
    panel.getByText("Refer a claim the manual flags for review."),
  ).toBeVisible();
  await expect(panel.getByText("GPT-6 Luna at low")).toBeVisible();
  await expect(panel.getByText("GPT-6 Luna at medium")).toBeVisible();
  await panel.getByRole("button", { name: "Approve the change" }).click();
  const dialog = page.getByRole("dialog", { name: "Approve the change?" });
  await dialog.getByRole("button", { name: "Approve the change" }).click();
  await expect
    .poll(() => started(request))
    .toContainEqual({
      review: {
        round_id: roundId,
        proposal_id: Number(proposal.proposal_id),
        handler_id: DANA,
        approved: true,
        note: "",
      },
    });

  // The service records the review and makes the version under test
  await review(request, roundId, Number(proposal.proposal_id), true);
  await send(request, `/api/rounds/${String(roundId)}/versions`);
  await expect(page.getByRole("status")).toHaveText("Evaluations, 1 of 3");
});

test("rejecting a recipe sends the reason, and Marcus sees no buttons", async ({
  page,
  request,
  browser,
}) => {
  await evaluations(request, roundId);
  await send(request, `/api/rounds/${String(roundId)}/verdict`);
  const recipe = await send(
    request,
    `/api/rounds/${String(roundId)}/proposals/recipes`,
    {
      recipe: "1. Call read_results.\n2. Look for a pattern first.",
      reason: "Rules for single claims didn't carry over.",
    },
  );

  await page.goto("/#/improvement");
  const panel = page.getByRole("region", {
    name: "A new recipe waits for your review",
  });
  await expect(panel.getByText("2. Look for a pattern first.")).toBeVisible();
  await panel
    .getByLabel(/^Why reject it\?/)
    .fill("Keep the step that reads the results.");
  await panel.getByRole("button", { name: "Reject the recipe" }).click();
  await expect
    .poll(() => started(request))
    .toContainEqual({
      review: {
        round_id: roundId,
        proposal_id: Number(recipe.proposal_id),
        handler_id: DANA,
        approved: false,
        note: "Keep the step that reads the results.",
      },
    });

  const marcus = await browser.newContext({
    storageState: SIGNED_IN.marcus,
  });
  const his = await marcus.newPage();
  await his.goto("/#/improvement");
  await expect(
    his.getByRole("region", { name: "A new recipe waits for your review" }),
  ).toBeVisible();
  await expect(
    his.getByRole("button", { name: /^(Start|Stop|Approve|Reject)/ }),
  ).toHaveCount(0);
  await expect(
    his.getByText(/can review the improver's proposals\. You're signed in/),
  ).toBeVisible();
  await marcus.close();
});
