import { expect, test } from "@playwright/test";
import { SIGNED_IN } from "./signed-in";

test("Dana changes the spending limit, which stays after a reload", async ({
  page,
}) => {
  await page.goto("/#/settings");
  const limit = page.getByRole("spinbutton", { name: /^Spending limit/ });
  await expect(limit).toHaveValue("0.5");
  await limit.fill("0.75");
  await page.getByRole("button", { name: "Save the changes" }).click();
  const dialog = page.getByRole("dialog", { name: "Change the settings?" });
  await expect(dialog.getByText("$0.75")).toBeVisible();
  await dialog.getByRole("button", { name: "Change the settings" }).click();
  await expect(page.getByText(/^Last changed by Dana Whitfield/)).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("spinbutton", { name: /^Spending limit/ }),
  ).toHaveValue("0.75");
});

test("the appearance stays after a reload, and Light holds under a dark computer", async ({
  page,
}) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/#/settings");
  await page.getByRole("button", { name: "Dark" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "Light" }).click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  const background = await page.evaluate(
    () => getComputedStyle(document.body).backgroundColor,
  );
  expect(background).toBe("rgb(240, 244, 245)");
});

test.describe("signed in as Marcus Oyelaran", () => {
  test.use({ storageState: SIGNED_IN.marcus });

  test("he sees the settings, can't save them, and is told why", async ({
    page,
  }) => {
    await page.goto("/#/settings");
    await expect(
      page.getByRole("spinbutton", { name: /^Approval limit/ }),
    ).toHaveAttribute("readonly", "");
    await expect(
      page.getByRole("button", { name: "Save the changes" }),
    ).toHaveCount(0);
    await expect(
      page.getByText(/can change the settings\. You're signed in as Marcus/),
    ).toBeVisible();
  });
});
