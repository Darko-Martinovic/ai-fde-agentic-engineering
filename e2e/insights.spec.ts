import { expect, test, type APIRequestContext } from "@playwright/test";

// The agent's steps and decisions are recorded through the API, so no model is called.
async function agentWorks(
  request: APIRequestContext,
  claimId: string,
  decision: { decision: "approve" | "decline"; payout: number },
  steps: [kind: "tool_call" | "tool_result" | "reply", text: string][],
) {
  await request.post(`/api/claims/${claimId}/start`);
  for (const [kind, text] of steps) {
    const response = await request.post(`/api/claims/${claimId}/steps`, {
      data: { thread_id: `${claimId}-e2e`, kind, text },
    });
    expect(response.ok()).toBe(true);
  }
  const response = await request.post(`/api/claims/${claimId}/decision`, {
    data: {
      ...decision,
      reasons: "Set up by the end-to-end test.",
      policy_section: "Section 4, Baggage Delay",
    },
  });
  expect(response.ok()).toBe(true);
}

test("the claim page shows the agent at work", async ({ page, request }) => {
  await agentWorks(request, "CLM-1007", { decision: "approve", payout: 1099 }, [
    ["tool_call", 'get_claim {"claim_id": "CLM-1007"}'],
    ["tool_result", '{"claim_id": "CLM-1007"}'],
    ["tool_call", 'pay_claim {"claim_id": "CLM-1007", "amount": 1099}'],
    [
      "tool_result",
      "Refused (409): A payout over $1,000.00 waits for a handler's sign-off",
    ],
    ["reply", "Approved $1,099.00, waiting for a handler's sign-off."],
  ]);
  await page.goto("/#/claims/CLM-1007");
  const steps = page.getByRole("list").filter({ hasText: "Calls a tool" });
  await expect(steps.getByRole("listitem")).toHaveCount(5);
  await expect(steps.getByText("pay_claim")).toBeVisible();
  await expect(steps.getByText(/^Refused \(409\)/)).toBeVisible();
  await expect(
    steps.getByText("Approved $1,099.00, waiting for a handler's sign-off."),
  ).toBeVisible();
});

test("Insights adds up the agent's work", async ({ page, request }) => {
  await agentWorks(request, "CLM-1004", { decision: "decline", payout: 0 }, [
    ["tool_call", 'get_claim {"claim_id": "CLM-1004"}'],
    ["tool_result", '{"claim_id": "CLM-1004"}'],
    ["tool_call", 'pay_claim {"claim_id": "CLM-1004", "amount": 186}'],
    ["tool_result", "Refused (409): Claim CLM-1004 is not approved"],
    ["reply", "Declined."],
  ]);
  await page.goto("/");
  await page.getByRole("link", { name: "Insights" }).click();
  await expect(page.getByText("Straight through")).toBeVisible();

  const run = page.getByRole("list", { name: "The latest run" });
  await expect(run.getByRole("link", { name: "CLM-1004" })).toBeVisible();
  await expect(run.getByLabel(/^Declined in/)).toBeVisible();

  const types = page.getByRole("list", { name: "Decisions by claim type" });
  const delay = types
    .getByRole("listitem")
    .filter({ hasText: "Baggage delay" });
  await expect(delay.getByLabel("Declined: 1")).toBeVisible();

  const tools = page.getByRole("list", { name: "Tool calls" });
  const pay = tools.getByRole("listitem").filter({ hasText: "pay_claim" });
  await expect(pay.getByLabel(/^Refused: \d+$/)).toBeVisible();

  await page.getByRole("table").getByRole("link", { name: "CLM-1004" }).click();
  await expect(page.getByText("What the agent did")).toBeVisible();
});
