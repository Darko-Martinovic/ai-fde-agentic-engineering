/** The shapes of rounds of improvement as the backend gives them: a round and
 *  where it has got to, the improver's proposals beside what they would
 *  change, and the recipe's versions. */

import type { EvaluationSet } from "./agentTypes";
import type { Hunk } from "./improvementTypes";

export type Stage =
  | "first_evaluations"
  | "improving"
  | "change_waiting"
  | "evaluating"
  | "verdict"
  | "recipe_waiting"
  | "finished"
  | "stopped";

export type RoundStatus = "open" | "finished" | "stopped";

/** What a version scored on a set, on average over its runs there. */
export interface Scores {
  accuracy: number;
  grade: number | null;
  cost_per_claim: number;
  seconds_per_claim: number;
}

export interface Proposal {
  proposal_id: number;
  round_id: number;
  kind: "change" | "recipe";
  /** A change's instructions, model and reasoning effort, or a recipe */
  proposed: {
    instructions?: string;
    model?: string;
    reasoning_effort?: string;
    recipe?: string;
  };
  reason: string;
  proposed_at: string;
  review: "approved" | "rejected" | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
}

/** The proposal waiting for a handler, beside what it would change: the
 *  lines, and for a change the model and reasoning effort before it. */
export interface WaitingProposal extends Proposal {
  changes: Hunk[];
  model_before: string | null;
  reasoning_effort_before: string | null;
}

/** How far a stage with steps has got: the step underway, of how many. */
export interface Progress {
  step: number;
  of: number;
}

export interface Round {
  round_id: number;
  started_by: string;
  started_at: string;
  settings_number: number;
  recipe_number: number;
  version_before: number;
  improver_model: string;
  thread_id: string;
  first_evaluations: EvaluationSet[];
  status: RoundStatus;
  stopped_by: string | null;
  stop_reason: string | null;
  finished_at: string | null;
  version_tried: number | null;
  verdict: "kept" | "rolled_back" | null;
  verdict_reason: string | null;
  /** The held-out scores of the version before and of the version tried */
  scores_before: Scores | null;
  scores_after: Scores | null;
  stage: Stage;
  progress: Progress | null;
  /** US dollars spent so far, of the round's limit */
  spent: number;
  spending_limit: number;
  proposals: Proposal[];
  waiting: WaitingProposal | null;
}

export interface Recipe {
  number: number;
  recipe: string;
  based_on: number | null;
  reason: string;
  proposed_by: string;
  round_id: number | null;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
}

export interface RecipeDetails extends Recipe {
  changes: Hunk[];
}

export interface Improvement {
  rounds: Round[];
  recipes: Recipe[];
  current_recipe: number;
}

export interface RoundStarted {
  round_id: number;
}

export interface Reviewing {
  round_id: number;
  proposal_id: number;
}
