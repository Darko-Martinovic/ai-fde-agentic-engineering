import { describe, expect, it } from "vitest";
import { parseRoute, paths } from "./paths";

describe("parseRoute", () => {
  it("knows the pages", () => {
    expect(parseRoute("")).toEqual({ page: "queue" });
    expect(parseRoute("#/")).toEqual({ page: "queue" });
    expect(parseRoute("#/instructions")).toEqual({ page: "instructions" });
    expect(parseRoute("#/insights")).toEqual({ page: "insights" });
    expect(parseRoute("#/claims/CLM-1001")).toEqual({
      page: "claim",
      claimId: "CLM-1001",
    });
    expect(parseRoute("#/claims/")).toEqual({ page: "queue" });
    expect(parseRoute("#/scoreboard")).toEqual({ page: "scoreboard" });
    expect(parseRoute("#/scoreboard/7")).toEqual({
      page: "evaluation",
      runId: 7,
    });
    expect(parseRoute("#/scoreboard/seven")).toEqual({ page: "queue" });
  });
});

it("builds the link the route reads back", () => {
  expect(parseRoute(paths.claim("CLM-1001"))).toEqual({
    page: "claim",
    claimId: "CLM-1001",
  });
  expect(parseRoute(paths.evaluation(12))).toEqual({
    page: "evaluation",
    runId: 12,
  });
});
