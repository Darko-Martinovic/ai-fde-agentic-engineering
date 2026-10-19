import { expect, test, type APIRequestContext } from "@playwright/test";

// The agent's decisions are set up through the API, so no model is called.
async function agentDecides(
  request: APIRequestContext,
  claimId: string,
  decision: "approve" | "refer",
  payout: number,
) {
  await request.post(`/api/claims/${claimId}/start`);
  const response = await request.post(`/api/claims/${claimId}/decision`, {
    data: {
      decision,
      payout,
      reasons: "Set up by the end-to-end test.",
      policy_section: "Section 5, Baggage and Personal Effects",
    },
  });
  expect(response.ok()).toBe(true);
}

test("the queue shows all 25 claims waiting", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "25 Waiting" })).toBeVisible();
  await expect(page.getByRole("row")).toHaveCount(26);
  await expect(page.getByText("25 of 25 claims")).toBeVisible();
});

test("a claim opens from the queue", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "CLM-1001" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Flight home canceled by the airline, rebooked the next morning",
    }),
  ).toBeVisible();
  await expect(page.getByText("Hotel receipt")).toBeVisible();
  await expect(page.getByText("UnderCover Premium")).toBeVisible();
});

test("a handler signs off a payout over $1,000", async ({ page, request }) => {
  await agentDecides(request, "CLM-1002", "approve", 1150);
  await page.goto("/#/claims/CLM-1002");
  await expect(page.getByText("Awaiting sign-off").first()).toBeVisible();
  await page.getByLabel("Handler").selectOption("HND-01");
  await page.getByRole("button", { name: "Sign off $1,150.00" }).click();
  await expect(page.getByText(/authorized by Dana Whitfield/)).toBeVisible();
  await page.getByRole("link", { name: "Back to the queue" }).click();
  await expect(page.getByRole("button", { name: "1 Decided" })).toBeVisible();
});

test("a handler decides a referral", async ({ page, request }) => {
  await agentDecides(request, "CLM-1010", "refer", 0);
  await page.goto("/#/claims/CLM-1010");
  await expect(page.getByText("Set up by the end-to-end test.")).toBeVisible();
  await page.getByLabel("Handler").selectOption("HND-02");
  await page.getByLabel("Payout in US dollars").fill("1350");
  await page.getByLabel("Reasons").fill("Covered emergency treatment.");
  await page.getByRole("button", { name: "Approve and pay $1,350.00" }).click();
  await expect(page.getByText(/authorized by Marcus Oyelaran/)).toBeVisible();
});
