import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ClaimPage } from "./ClaimPage";
import { claim, mockFetch } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the claim's heading", async () => {
  mockFetch({ "GET /api/claims/CLM-1001": claim() });
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByRole("heading", {
      name: "Flight home canceled by the airline",
    }),
  ).toBeDefined();
  expect(screen.getByText("Waiting")).toBeDefined();
  expect(screen.getByText("$325.00")).toBeDefined();
});

it("shows when the claim can't load", async () => {
  mockFetch({});
  render(<ClaimPage claimId="CLM-9999" />);
  expect(
    await screen.findByText("No route for GET /api/claims/CLM-9999"),
  ).toBeDefined();
});
