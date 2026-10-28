import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { InstructionsPage } from "./Instructions";
import { mockFetch } from "../testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the instructions and the policy wording", async () => {
  mockFetch({
    "GET /api/instructions":
      "# UnderCover claim agent\n\nRead the claim with `get_claim`.",
    "GET /api/policy-wording":
      "# Policy Wording\n\n| Benefit | Economy |\n|---|---|\n| Deductible | $100 |",
  });
  render(<InstructionsPage />);
  expect(
    await screen.findByRole("heading", { name: "UnderCover claim agent" }),
  ).toBeDefined();
  expect(screen.getByText("get_claim").tagName).toBe("CODE");
  expect(await screen.findByRole("cell", { name: "$100" })).toBeDefined();
  expect(screen.getByText("The policy wording")).toBeDefined();
});

it("shows when the instructions can't load", async () => {
  mockFetch({});
  render(<InstructionsPage />);
  expect(
    await screen.findByText("No route for GET /api/instructions"),
  ).toBeDefined();
});
