import { expect, test, type APIRequestContext } from "@playwright/test";
import { AS_THE_AGENT } from "./agent-key";
import { startClaim } from "./claim-starts";
import { SIGNED_IN } from "./signed-in";
import { resumed } from "./stand-in";

// The agent's decisions are set up through the API, so no model is called.
async function agentDecides(
  request: APIRequestContext,
  claimId: string,
  decision: "approve" | "refer",
  payout: number,
) {
  await startClaim(request, claimId);
  const response = await request.post(`/api/claims/${claimId}/decision`, {
    headers: AS_THE_AGENT,
    data: {
      decision,
      payout,
      reasons: "Set up by the end-to-end test.",
      policy_section: "Section 5, Baggage and Personal Effects",
    },
  });
  expect(response.ok()).toBe(true);
}

// The queue's 25 claims and CLM-1901, the security team's
test("the queue shows all 26 claims waiting", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "26 Waiting" })).toBeVisible();
  await expect(page.getByRole("row")).toHaveCount(27);
  await expect(page.getByText("26 of 26 claims")).toBeVisible();
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

/** The claims the stand-in for the agent's service was asked to pick back up. */
test("a sign-off pays the claim, and the agent is told", async ({
  page,
  request,
}) => {
  await agentDecides(request, "CLM-1020", "approve", 1350);
  expect(
    (
      await request.post("/api/claims/CLM-1020/payment", {
        headers: AS_THE_AGENT,
        data: { amount: 1350 },
      })
    ).status(),
  ).toBe(403);
  await page.goto("/#/claims/CLM-1020");
  await expect(page.getByText("Awaiting sign-off").first()).toBeVisible();
  await page.getByRole("button", { name: "Sign off $1,350.00" }).click();
  await expect(
    page.getByText(/Paid \$1,350\.00, signed off by Dana Whitfield at/),
  ).toBeVisible();
  await expect(page.getByText("Decided").first()).toBeVisible();
  await expect.poll(() => resumed(request)).toContain("CLM-1020");
});

test("a rejection goes back to the agent with its note", async ({
  page,
  request,
}) => {
  await agentDecides(request, "CLM-1002", "approve", 1150);
  await page.goto("/#/claims/CLM-1002");
  await page
    .getByLabel("Note for the agent")
    .fill("The wool suit is limited to $300.00.");
  await page.getByRole("button", { name: "Reject" }).click();
  await expect(
    page.getByText(
      /Rejected by Dana Whitfield at .*: The wool suit is limited to \$300\.00\./,
    ),
  ).toBeVisible();
  await expect(page.getByText("In progress").first()).toBeVisible();
  await expect.poll(() => resumed(request)).toContain("CLM-1002");
});

test("a handler decides a referral", async ({ page, request }) => {
  await agentDecides(request, "CLM-1010", "refer", 0);
  await page.goto("/#/claims/CLM-1010");
  await expect(page.getByText("Set up by the end-to-end test.")).toBeVisible();
  await page.getByLabel("Payout in US dollars").fill("1350");
  await page.getByLabel("Reasons").fill("Covered emergency treatment.");
  await page.getByRole("button", { name: "Approve and pay $1,350.00" }).click();
  await expect(page.getByText(/authorized by Dana Whitfield/)).toBeVisible();
});

test("signing out lands on the sign-in page", async ({ page }) => {
  await page.goto("/#/insights");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.goto("/#/scoreboard");
  await expect(page).toHaveURL(/#\/sign-in\?next=%23%2Fscoreboard$/);
});

test.describe("signed in as Marcus Oyelaran", () => {
  test.use({ storageState: SIGNED_IN.marcus });

  test("he sees why he can't review a held payout", async ({
    page,
    request,
  }) => {
    await agentDecides(request, "CLM-1021", "approve", 2100);
    await page.goto("/#/claims/CLM-1021");
    await expect(
      page.getByText(
        "Only a handler who can sign off payouts over the approval limit can review this payout. You're signed in as Marcus Oyelaran, who can't.",
      ),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: /Sign off/ })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Reject" })).toHaveCount(0);
  });
});
