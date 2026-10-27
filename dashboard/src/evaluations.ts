import type { EvaluationSet, Measures, RunFacts } from "./api";
import { NOTHING, cost, duration, money, percent } from "./format";

// The reasoning effort a run records for a model run without one
const NO_REASONING = "none";

/* How an evaluation and its measures read on the scoreboard. */

export const SET_LABELS: Record<EvaluationSet, string> = {
  evaluation: "Evaluation set",
  held_out: "Held-out set",
};

/** A share, such as 0.8, as a whole percentage: 80%. */
function share(fraction: number): string {
  return percent(fraction, 1);
}

/** The model a run worked on, with its reasoning effort if it had one. */
export function modelWithEffort(label: string, effort: string): string {
  return effort === NO_REASONING ? label : `${label}, ${effort} reasoning`;
}

/** Which claims an evaluation worked: its set, and all of it or its tiny ones. */
export function whichClaims(run: RunFacts, count: number): string {
  const set = run.evaluation_set ? SET_LABELS[run.evaluation_set] : "";
  const size = run.tiny ? `${String(count)} tiny` : `all ${String(count)}`;
  return `${set}, ${size}`;
}

/** The lab's measures, each with its label and how it reads. */
export function measureCells(
  measures: Measures,
): { label: string; value: string }[] {
  return [
    { label: "Decision accuracy", value: share(measures.decision_accuracy) },
    { label: "Accuracy", value: share(measures.accuracy) },
    { label: "Cost of mistakes", value: money(measures.cost_of_mistakes) },
    { label: "Straight through", value: share(measures.straight_through) },
    {
      label: "Model cost per claim",
      value: cost(measures.model_cost_per_claim),
    },
    { label: "Time per claim", value: duration(measures.seconds_per_claim) },
    {
      label: "Time for the run",
      value:
        measures.run_seconds === null
          ? NOTHING
          : duration(measures.run_seconds),
    },
  ];
}
