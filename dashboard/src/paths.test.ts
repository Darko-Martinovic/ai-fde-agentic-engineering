import { describe, expect, it } from "vitest";
import { parseRoute, paths } from "./paths";

describe("parseRoute", () => {
  it("knows the four pages", () => {
    expect(parseRoute("")).toEqual({ page: "queue" });
    expect(parseRoute("#/")).toEqual({ page: "queue" });
    expect(parseRoute("#/instructions")).toEqual({ page: "instructions" });
    expect(parseRoute("#/insights")).toEqual({ page: "insights" });
    expect(parseRoute("#/claims/CLM-1001")).toEqual({
      page: "claim",
      claimId: "CLM-1001",
    });
    expect(parseRoute("#/claims/")).toEqual({ page: "queue" });
  });
});

it("builds the link the route reads back", () => {
  expect(parseRoute(paths.claim("CLM-1001"))).toEqual({
    page: "claim",
    claimId: "CLM-1001",
  });
});
