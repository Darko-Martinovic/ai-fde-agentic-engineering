import type { Page } from "@playwright/test";
import { setting } from "../settings/settings.config.ts";

// Each handler's browser storage, with their session, which the sign-in
// setup keeps for the tests (git-ignored).
export const SIGNED_IN = {
  dana: "e2e/.auth/dana.json",
  marcus: "e2e/.auth/marcus.json",
};

export const EMAILS = {
  dana: "dana.whitfield@undercover.example",
  marcus: "marcus.oyelaran@undercover.example",
};

/** Sign in on the sign-in page with the stand-in's password. */
export async function signIn(page: Page, email: string, password?: string) {
  await page.goto("/#/sign-in");
  await page.getByLabel("Email").fill(email);
  await page
    .getByLabel("Password")
    .fill(password ?? setting("E2E_HANDLER_PASSWORD"));
  await page.getByRole("button", { name: "Sign in" }).click();
}
