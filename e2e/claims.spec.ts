import { expect, test, type APIRequestContext } from "@playwright/test";
import { setting } from "../settings/settings.config";
import { startClaim } from "./claim-starts";

// The stand-in for the agent's service, which playwright.config.ts starts
const AGENT = setting("E2E_AGENT_URL");

// The agent's decisions are set up through the API, so no model is called.
async function agentDecides(
  request: APIRequestContext,
  claimId: string,
  decision: "approve" | "refer",
  payout: number,
) {
  await startClaim(request, claimId);
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

/** The claims the stand-in for the agent's service was asked to pick back up. */
async function resumed(request: APIRequestContext): Promise<string[]> {
  return (await (await request.get(`${AGENT}/api/resumed`)).json()) as string[];
}

test("a sign-off reaches the agent, which pays the claim", async ({
  page,
  request,
}) => {
  await agentDecides(request, "CLM-1020", "approve", 1350);
  expect(
    (
      await request.post("/api/claims/CLM-1020/payment", {
        data: { amount: 1350 },
      })
    ).status(),
  ).toBe(409);
  await page.goto("/#/claims/CLM-1020");
  await expect(page.getByText("Awaiting sign-off").first()).toBeVisible();
  await page.getByLabel("Handler").selectOption("HND-01");
  await page.getByRole("button", { name: "Sign off $1,350.00" }).click();
  await expect(page.getByText(/Signed off by Dana Whitfield/)).toBeVisible();
  await expect(page.getByText("In progress").first()).toBeVisible();
  await expect.poll(() => resumed(request)).toContain("CLM-1020");
  // The test plays the agent's part and pays, as the graph would
  const paid = await request.post("/api/claims/CLM-1020/payment", {
    data: { amount: 1350 },
  });
  expect(paid.ok()).toBe(true);
  await expect(
    page.getByText(/Paid \$1,350\.00, signed off by Dana Whitfield at/),
  ).toBeVisible();
  await expect(page.getByText("Decided").first()).toBeVisible();
});

test("a rejection goes back to the agent with its note", async ({
  page,
  request,
}) => {
  await agentDecides(request, "CLM-1002", "approve", 1150);
  await page.goto("/#/claims/CLM-1002");
  await page.getByLabel("Handler").selectOption("HND-02");
  await page
    .getByLabel("Note for the agent")
    .fill("The wool suit is limited to $300.00.");
  await page.getByRole("button", { name: "Reject" }).click();
  await expect(
    page.getByText(
      /Rejected by Marcus Oyelaran at .*: The wool suit is limited to \$300\.00\./,
    ),
  ).toBeVisible();
  await expect(page.getByText("In progress").first()).toBeVisible();
  await expect.poll(() => resumed(request)).toContain("CLM-1002");
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
