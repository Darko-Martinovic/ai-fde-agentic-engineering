import { cleanup, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { RecipePage } from "./RecipePage";
import {
  HANDLERS,
  RECIPE_1,
  mockFetch,
  recipeProposal,
  renderAs,
} from "../testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows what a recipe changed, why, and who approved it", async () => {
  mockFetch({
    "GET /api/improvement/recipes/2": {
      ...RECIPE_1,
      number: 2,
      recipe: "1. Read the results.\n2. Look for a pattern first.",
      based_on: 1,
      reason: "Rules for single claims didn't carry over.",
      proposed_by: "Round 1",
      round_id: 1,
      approved_by: "HND-01",
      approved_at: "2026-10-28T10:30:00Z",
      changes: recipeProposal().changes,
    },
    "GET /api/handlers": HANDLERS,
  });
  renderAs(<RecipePage number={2} />);
  expect(
    await screen.findByRole("heading", { level: 1, name: "Recipe 2" }),
  ).toBeDefined();
  expect(screen.getByRole("link", { name: "Recipe 1" })).toBeDefined();
  expect(
    await screen.findByText(/^Dana Whitfield, Oct 28, 2026/),
  ).toBeDefined();
  const diff = screen.getByRole("group", { name: "Changes in recipe 2" });
  expect(within(diff).getByText("2. Look for a pattern first.")).toBeDefined();
});

it("shows the first recipe as nobody's change, and a missing one's error", async () => {
  mockFetch({ "GET /api/improvement/recipes/1": RECIPE_1 });
  renderAs(<RecipePage number={1} />);
  expect(await screen.findByText("Nothing: the first recipe")).toBeDefined();
  expect(screen.getByText("Not needed")).toBeDefined();
  expect(screen.getByText("No change to the text.")).toBeDefined();
  cleanup();
  mockFetch({
    "GET /api/improvement/recipes/9": Response.json(
      { detail: "Recipe 9 not found" },
      { status: 404 },
    ),
  });
  renderAs(<RecipePage number={9} />);
  const alert = await screen.findByRole("alert");
  expect(alert.textContent).toContain("Recipe 9 not found");
  expect(
    within(alert).getByRole("button", { name: "Try again" }),
  ).toBeDefined();
});
