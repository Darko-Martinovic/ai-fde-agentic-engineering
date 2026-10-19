import { describe, expect, it } from "vitest";
import {
  claimTypes,
  countByStatus,
  filterClaims,
  sortClaims,
  totals,
} from "./filters";
import { QUEUE } from "./testing";

const ids = (claims: { claim_id: string }[]) => claims.map((c) => c.claim_id);

describe("filterClaims", () => {
  const all = { status: "all", type: "all", search: "" } as const;

  it("keeps everything with no filters", () => {
    expect(filterClaims(QUEUE, all)).toHaveLength(4);
  });

  it("filters by state and type", () => {
    expect(ids(filterClaims(QUEUE, { ...all, status: "decided" }))).toEqual([
      "CLM-1003",
      "CLM-1005",
    ]);
    expect(ids(filterClaims(QUEUE, { ...all, type: "baggage" }))).toEqual([
      "CLM-1002",
    ]);
  });

  it("searches ids, customers and types", () => {
    expect(ids(filterClaims(QUEUE, { ...all, search: " tom " }))).toEqual([
      "CLM-1002",
    ]);
    expect(ids(filterClaims(QUEUE, { ...all, search: "1005" }))).toEqual([
      "CLM-1005",
    ]);
    expect(ids(filterClaims(QUEUE, { ...all, search: "medical" }))).toEqual([
      "CLM-1003",
    ]);
  });
});

describe("sortClaims", () => {
  it("sorts numbers, with no payout first", () => {
    const sorted = sortClaims(QUEUE, { key: "payout", ascending: true });
    expect(ids(sorted)).toEqual([
      "CLM-1001",
      "CLM-1003",
      "CLM-1005",
      "CLM-1002",
    ]);
  });

  it("sorts text both ways", () => {
    const sorted = sortClaims(QUEUE, {
      key: "customer_name",
      ascending: false,
    });
    expect(ids(sorted)).toEqual([
      "CLM-1002",
      "CLM-1005",
      "CLM-1001",
      "CLM-1003",
    ]);
  });
});

it("counts each state", () => {
  expect(countByStatus(QUEUE)).toEqual({
    waiting: 1,
    in_progress: 0,
    awaiting_sign_off: 1,
    referred: 0,
    decided: 2,
  });
});

it("adds up what is claimed, paid and held", () => {
  expect(totals(QUEUE)).toEqual({ claimed: 5613, paid: 243, held: 1150 });
});

it("lists the claim types in order", () => {
  expect(claimTypes(QUEUE)).toEqual([
    "baggage",
    "emergency_medical",
    "passport",
    "trip_delay",
  ]);
});
