import { expect, it } from "vitest";
import { claimsDone, summaryLines } from "./runs";
import { run, runClaim } from "./testing";

it("counts a dispatch's claims done out of all it takes", () => {
  expect(claimsDone(run())).toEqual({ done: 1, total: 2 });
  const waiting = runClaim({ claim_id: "CLM-1003", status: "waiting" });
  const held = runClaim({ claim_id: "CLM-1008", status: "awaiting_sign_off" });
  expect(claimsDone(run({ claims: [waiting, held] }))).toEqual({
    done: 1,
    total: 2,
  });
});

it("sums up what a dispatch left, line by line", () => {
  expect(
    summaryLines({
      approved: 3,
      declined: 1,
      referred: 1,
      waiting_for_sign_off: [
        { claim_id: "CLM-1008", payout: 2240 },
        { claim_id: "CLM-1011", payout: 1150 },
      ],
      left_for_handler: ["CLM-1016"],
      unfinished: ["CLM-1012"],
    }),
  ).toEqual([
    "3 approved, 1 declined and 1 referred.",
    "Waiting for sign-off: CLM-1008 $2,240.00, CLM-1011 $1,150.00",
    "Left for a handler: CLM-1016",
    "Left for the next dispatch: CLM-1012",
  ]);
});

it("leaves out the lines with nothing in them", () => {
  expect(
    summaryLines({
      approved: 0,
      declined: 2,
      referred: 0,
      waiting_for_sign_off: [],
      left_for_handler: [],
      unfinished: [],
    }),
  ).toEqual(["0 approved, 2 declined and 0 referred."]);
});
