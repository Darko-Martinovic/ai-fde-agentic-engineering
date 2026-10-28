import { expect, test as setup } from "@playwright/test";
import { EMAILS, SIGNED_IN, signIn } from "./signed-in";

setup("sign in as Dana Whitfield", async ({ page }) => {
  await signIn(page, EMAILS.dana);
  await expect(
    page.getByRole("banner").getByText("Dana Whitfield"),
  ).toBeVisible();
  await page.context().storageState({ path: SIGNED_IN.dana });
});

setup("sign in as Marcus Oyelaran", async ({ page }) => {
  await signIn(page, EMAILS.marcus);
  await expect(
    page.getByRole("banner").getByText("Marcus Oyelaran"),
  ).toBeVisible();
  await page.context().storageState({ path: SIGNED_IN.marcus });
});
