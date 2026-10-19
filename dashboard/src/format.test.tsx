import { expect, it } from "vitest";
import { STATUSES, clock, date, humanize, money } from "./format";

it("writes money in US dollars", () => {
  expect(money(1150)).toBe("$1,150.00");
  expect(money(0)).toBe("$0.00");
});

it("writes dates without shifting them across time zones", () => {
  expect(date("2026-06-24")).toBe("Jun 24, 2026");
  expect(date("2026-06-24T23:59:00Z")).toBe("Jun 24, 2026");
});

it("writes a time of day", () => {
  expect(clock("2026-06-24T15:21:24Z")).toMatch(/\d{1,2}:\d{2}:\d{2}/);
});

it("turns codes into labels", () => {
  expect(humanize("emergency_medical")).toBe("Emergency medical");
  expect(STATUSES).toHaveLength(5);
});
