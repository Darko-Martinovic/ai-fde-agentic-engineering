import { expect, it } from "vitest";
import {
  STATUSES,
  clock,
  date,
  duration,
  humanize,
  money,
  percent,
  pretty,
} from "./format";

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

it("indents JSON and leaves other text alone", () => {
  expect(pretty('{"a":1}')).toBe('{\n  "a": 1\n}');
  expect(pretty("Refused (409)")).toBe("Refused (409)");
});

it("writes a span of time", () => {
  expect(duration(7.4)).toBe("7 s");
  expect(duration(60)).toBe("1 min");
  expect(duration(125)).toBe("2 min 5 s");
});

it("writes a share as a percentage", () => {
  expect(percent(2, 3)).toBe("67%");
  expect(percent(0, 0)).toBe("—");
});
