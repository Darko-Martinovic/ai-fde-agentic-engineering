import type {
  Improvement,
  RecipeDetails,
  Round,
  Scores,
  WaitingProposal,
} from "./api";

/* Test fixtures for rounds of improvement: a round at each stage, the
 * improver's proposals and the recipe's versions. */

export function scores(overrides: Partial<Scores> = {}): Scores {
  return {
    accuracy: 0.6,
    grade: 1.5,
    cost_per_claim: 0.001,
    seconds_per_claim: 20,
    ...overrides,
  };
}

/** A change to Gemini at minimal, with one line of the instructions changed,
 *  waiting in round 1. */
export function changeProposal(
  overrides: Partial<WaitingProposal> = {},
): WaitingProposal {
  return {
    proposal_id: 1,
    round_id: 1,
    kind: "change",
    proposed: {
      instructions: "# UnderCover claim agent\n\nRefer what the manual flags.",
      model: "google/gemini-3.5-flash-lite",
      reasoning_effort: "minimal",
    },
    reason: "Fewer wrong approvals of claims the manual flags.",
    proposed_at: "2026-10-28T10:00:00Z",
    review: null,
    reviewed_by: null,
    reviewed_at: null,
    review_note: null,
    changes: [
      {
        heading: "@@ -1,3 +1,3 @@",
        lines: [
          { kind: "context", text: "# UnderCover claim agent" },
          { kind: "removed", text: "Decide the claim." },
          { kind: "added", text: "Refer what the manual flags." },
        ],
      },
    ],
    model_before: "openai/gpt-6-luna",
    reasoning_effort_before: "low",
    ...overrides,
  };
}

/** A new recipe with one step added, waiting in round 1. */
export function recipeProposal(
  overrides: Partial<WaitingProposal> = {},
): WaitingProposal {
  return changeProposal({
    proposal_id: 2,
    kind: "recipe",
    proposed: { recipe: "1. Read the results.\n2. Look for a pattern first." },
    reason: "Rules for single claims didn't carry over.",
    changes: [
      {
        heading: "@@ -1 +1,2 @@",
        lines: [
          { kind: "context", text: "1. Read the results." },
          { kind: "added", text: "2. Look for a pattern first." },
        ],
      },
    ],
    model_before: null,
    reasoning_effort_before: null,
    ...overrides,
  });
}

/** Round 1, open in its first evaluations, 2 of 3, started by Dana
 *  Whitfield, $0.12 spent of its $0.50. */
export function round(overrides: Partial<Round> = {}): Round {
  return {
    round_id: 1,
    started_by: "HND-01",
    started_at: "2026-10-28T09:45:00Z",
    settings_number: 2,
    recipe_number: 1,
    version_before: 1,
    improver_model: "openai/gpt-6-luna",
    thread_id: "improver-1a2b3c4d",
    first_evaluations: ["evaluation", "held_out", "held_out"],
    status: "open",
    stopped_by: null,
    stop_reason: null,
    finished_at: null,
    version_tried: null,
    verdict: null,
    verdict_reason: null,
    scores_before: null,
    scores_after: null,
    stage: "first_evaluations",
    progress: { step: 2, of: 3 },
    spent: 0.12,
    spending_limit: 0.5,
    proposals: [],
    waiting: null,
    ...overrides,
  };
}

/** A round that tried version `version` and kept it or rolled it back. */
export function judgedRound(
  roundId: number,
  version: number,
  kept: boolean,
  accuracy: number,
): Round {
  return round({
    round_id: roundId,
    status: "finished",
    stage: "finished",
    progress: null,
    finished_at: "2026-10-28T11:00:00Z",
    version_before: 1,
    version_tried: version,
    verdict: kept ? "kept" : "rolled_back",
    verdict_reason: kept
      ? "accuracy improved"
      : "no score improved by more than the noise",
    scores_before: scores(),
    scores_after: scores({ accuracy, grade: kept ? 1.9 : 1.4 }),
    proposals: [
      changeProposal({
        round_id: roundId,
        review: "approved",
        reviewed_by: "HND-01",
        reviewed_at: "2026-10-28T10:05:00Z",
      }),
    ],
  });
}

export const RECIPE_1: RecipeDetails = {
  number: 1,
  recipe: "1. Read the results.",
  based_on: null,
  reason: "The lab's first recipe, which fixes mistakes one at a time.",
  proposed_by: "The claims team",
  round_id: null,
  approved_by: null,
  approved_at: null,
  created_at: "2026-10-28T08:00:00Z",
  changes: [],
};

export function improvement(rounds: Round[] = []): Improvement {
  return { rounds, recipes: [RECIPE_1], current_recipe: 1 };
}
