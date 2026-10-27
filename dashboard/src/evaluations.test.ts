import { expect, it } from "vitest";
import { measureCells, modelWithEffort, whichClaims } from "./evaluations";
import { evaluation } from "./testing";

it("formats the measures as the scoreboard shows them", () => {
  const cells = measureCells(evaluation().measures);
  expect(cells.map((c) => c.value)).toEqual([
    "80%",
    "40%",
    "$1,600.00",
    "60%",
    "$0.0125",
    "40 s",
    "2 min 41 s",
  ]);
  const unfinished = { ...evaluation().measures, run_seconds: null };
  expect(measureCells(unfinished).at(-1)?.value).toBe("—");
});

it("names the claims an evaluation worked", () => {
  expect(whichClaims(evaluation(), 5)).toBe("Held-out set, 5 tiny");
  const whole = evaluation({ evaluation_set: "evaluation", tiny: false });
  expect(whichClaims(whole, 25)).toBe("Evaluation set, all 25");
});

it("names the model with its reasoning effort, if it had one", () => {
  expect(modelWithEffort("GPT-6 Luna", "low")).toBe(
    "GPT-6 Luna, low reasoning",
  );
  expect(modelWithEffort("Qwen 3.5 4B (local)", "none")).toBe(
    "Qwen 3.5 4B (local)",
  );
});
