import { describe, expect, it } from "vitest";
import { parseRoute, paths } from "./paths";

describe("parseRoute", () => {
  it("knows the pages", () => {
    expect(parseRoute("")).toEqual({ page: "queue" });
    expect(parseRoute("#/")).toEqual({ page: "queue" });
    expect(parseRoute("#/configuration")).toEqual({ page: "configuration" });
    expect(parseRoute("#/settings")).toEqual({ page: "settings" });
    expect(parseRoute("#/instructions")).toEqual({ page: "configuration" });
    expect(parseRoute("#/configuration/versions/3")).toEqual({
      page: "version",
      number: 3,
    });
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
    expect(parseRoute("#/sign-in")).toEqual({
      page: "sign-in",
      next: "#/",
    });
  });
});

it("goes on from the sign-in page to the page asked for", () => {
  expect(parseRoute(paths.signIn("#/scoreboard/7"))).toEqual({
    page: "sign-in",
    next: "#/scoreboard/7",
  });
  expect(parseRoute(paths.signIn(paths.signIn("#/insights")))).toEqual({
    page: "sign-in",
    next: "#/",
  });
  expect(parseRoute(paths.signIn("https://elsewhere"))).toEqual({
    page: "sign-in",
    next: "#/",
  });
  expect(parseRoute("#/sign-in?next=%E0")).toEqual({
    page: "sign-in",
    next: "#/",
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
  expect(parseRoute(paths.version(2))).toEqual({ page: "version", number: 2 });
});
