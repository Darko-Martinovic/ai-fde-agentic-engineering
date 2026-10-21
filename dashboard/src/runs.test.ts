import { expect, it } from "vitest";
import type { ClaimStatus, Step } from "./api";
import { latestAttempt, progress } from "./runs";
import { run } from "./testing";

const AT_TWO_MINUTES = new Date("2026-10-21T10:02:00Z").getTime();

// CLM-1001 done, CLM-1002 being worked, and three more waiting for the cap of 5
const WORKING: [string, ClaimStatus][] = [
  ["CLM-1001", "decided"],
  ["CLM-1002", "in_progress"],
  ["CLM-1003", "waiting"],
  ["CLM-1004", "waiting"],
  ["CLM-1005", "waiting"],
];

function statuses(entries: [string, ClaimStatus][]) {
  return new Map(entries);
}

it("counts the claims done and paces the time left on them", () => {
  expect(progress(run(), statuses(WORKING), AT_TWO_MINUTES)).toEqual({
    done: 1,
    total: 5,
    current: "CLM-1002",
    elapsed: 120,
    secondsLeft: 480,
  });
});

it("works out of fewer claims than the cap when fewer are waiting", () => {
  const done = progress(run(), statuses(WORKING.slice(0, 3)), AT_TWO_MINUTES);
  expect(done.total).toBe(3);
  expect(done.secondsLeft).toBe(240);
});

it("gives no time left before the first claim is done", () => {
  const done = progress(
    run({ claims_started: ["CLM-1001"] }),
    statuses([["CLM-1001", "in_progress"]]),
    AT_TWO_MINUTES,
  );
  expect(done.secondsLeft).toBeNull();
  expect(done.current).toBe("CLM-1001");
});

it("doesn't count a claim back in the queue after a failure or a Stop", () => {
  const done = progress(
    run({ status: "stopped", finished_at: "2026-10-21T10:01:00Z" }),
    statuses([
      ["CLM-1001", "decided"],
      ["CLM-1002", "waiting"],
    ]),
    AT_TWO_MINUTES,
  );
  expect(done.done).toBe(1);
  expect(done.current).toBeNull();
  expect(done.secondsLeft).toBeNull();
  expect(done.elapsed).toBe(60);
});

it("counts nothing done before the claims' states are known", () => {
  const done = progress(run(), statuses([]), AT_TWO_MINUTES);
  expect(done).toMatchObject({ done: 0, total: 5, current: null });
  expect(done.secondsLeft).toBeNull();
});

function step(thread: string, kind: Step["kind"] = "reply"): Step {
  return {
    thread_id: thread,
    kind,
    text: thread,
    recorded_at: "2026-10-21T10:00:00Z",
  };
}

it("keeps only the latest attempt's steps", () => {
  expect(latestAttempt([step("a"), step("b"), step("b")])).toHaveLength(2);
  expect(latestAttempt([])).toEqual([]);
});

it("shows no steps for an attempt that has only just started after a failure", () => {
  expect(latestAttempt([step("a"), step("a", "failure")])).toEqual([]);
});
