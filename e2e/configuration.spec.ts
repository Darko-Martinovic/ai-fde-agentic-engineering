import { expect, test } from "@playwright/test";

test("the header's Configuration link shows version 1 as current", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Configuration" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Configuration" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Current version: 1" }),
  ).toBeVisible();
  const row = page
    .getByRole("table", { name: "Versions" })
    .getByRole("row")
    .filter({ hasText: "Version 1" });
  await expect(row.getByText("Current")).toBeVisible();
  await expect(row.getByText("GPT-6 Luna")).toBeVisible();
  await page
    .getByText("The claim agent's instructions", { exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "UnderCover claim agent" }),
  ).toBeVisible();
  await row.getByRole("link", { name: "Version 1" }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Version 1" }),
  ).toBeVisible();
  await expect(page.getByText("No change to the text.")).toBeVisible();
});
