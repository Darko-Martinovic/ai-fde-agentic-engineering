/** How the Improvement page words a round: where it has got to, its verdict,
 *  what it has spent and its scores. */

import type {
  HandlerName,
  Proposal,
  Round,
  Scores,
  Stage,
  Version,
} from "./api";
import { cost, money, NOTHING, when } from "./format";
import { who } from "./handlerNames";

/** The steps of an open round, in order. */
export const STEPS: Stage[] = [
  "first_evaluations",
  "improving",
  "change_waiting",
  "evaluating",
  "verdict",
  "recipe_waiting",
];

export const STAGE_LABELS: Record<Stage, string> = {
  first_evaluations: "First evaluations",
  improving: "The improver at work",
  change_waiting: "A change waiting for approval",
  evaluating: "Evaluations",
  verdict: "Verdict",
  recipe_waiting: "A recipe waiting for approval",
  finished: "Finished",
  stopped: "Stopped",
};

/** Where a round has got to, with how far a stage with steps has got, such
 *  as "First evaluations, 2 of 3". */
export function stageLabel(round: Round): string {
  const label = STAGE_LABELS[round.stage];
  if (!round.progress) return label;
  const { step, of } = round.progress;
  return `${label}, ${String(step)} of ${String(of)}`;
}

/** The verdict on the version a round tried, and why, or that it tried none. */
export function verdictLine(round: Round): string {
  if (round.version_tried === null) return "No version tried";
  const version = `version ${String(round.version_tried)}`;
  if (round.verdict === null)
    return `Version ${String(round.version_tried)} under test`;
  const done = round.verdict === "kept" ? "Kept" : "Rolled back";
  return `${done} ${version}: ${round.verdict_reason ?? ""}`;
}

/** What a round has spent against its limit, such as "$0.1200 of $0.50". */
export function spentLine(round: Round): string {
  return `${cost(round.spent)} of ${money(round.spending_limit)}`;
}

/** What a score line shows: a held-out accuracy and grade. */
type Shown = Pick<Scores, "accuracy" | "grade">;

/** A version's held-out accuracy and grade, or none before a round has
 *  evaluated it. */
export function heldOutOf(version: Version): Shown | null {
  if (version.held_out_accuracy === null) return null;
  return {
    accuracy: version.held_out_accuracy,
    grade: version.held_out_grade,
  };
}

/** A held-out accuracy, such as "72%", or nothing without scores. */
export function accuracyLine(scores: Shown | null): string {
  return scores ? `${String(Math.round(scores.accuracy * 100))}%` : NOTHING;
}

/** A held-out grade, from 0 (F) to 3 (A), or nothing without one. */
export function gradeLine(scores: Shown | null): string {
  const grade = scores?.grade ?? null;
  return grade === null ? NOTHING : grade.toFixed(2);
}

const KINDS = { change: "Change", recipe: "Recipe" } as const;

/** Who reviewed a proposal and when, such as "Change approved by Dana
 *  Whitfield, Oct 28, 2026 10:02:11 AM", or that it waits. */
export function reviewLine(
  proposal: Proposal,
  handlers: HandlerName[],
): string {
  const kind = KINDS[proposal.kind];
  if (proposal.review === null || !proposal.reviewed_by) {
    return `${kind} waiting for a review`;
  }
  const at = proposal.reviewed_at ? `, ${when(proposal.reviewed_at)}` : "";
  return `${kind} ${proposal.review} by ${who(proposal.reviewed_by, handlers)}${at}`;
}

/** How a round ended, for one that has: who or what stopped it, or that it
 *  finished. */
export function endLine(round: Round): string | null {
  if (round.status === "stopped") return round.stop_reason ?? "Stopped";
  if (round.status === "finished") return "Finished with no version tried";
  return null;
}
