import type { ClaimStatus, ClaimSummary, DecisionKind } from "./claimTypes";

/* What the agent's runs and its work look like, as the backend sends them. */

export type RunStatus = "running" | "finished" | "stopped";

/** What the agent's service says when it takes a start or a stop. */
export interface Started {
  agents: number;
  model: string;
}

export interface Stopping {
  stopping: boolean;
}

export interface RunUsage {
  model_calls: number;
  input_tokens: number;
  output_tokens: number;
  cost: number;
}

/** A dispatch's claim: its line in the queue, with its work in the dispatch. */
export interface RunClaim extends ClaimSummary {
  started_at: string | null;
  seconds: number;
  model_cost: number;
}

/** What a dispatch left when it finished, each claim counted once. */
export interface RunSummary {
  approved: number;
  declined: number;
  referred: number;
  waiting_for_sign_off: { claim_id: string; payout: number }[];
  left_for_handler: string[];
  unfinished: string[];
}

/** The labelled sets an evaluation works copies of. */
export type EvaluationSet = "evaluation" | "held_out";

/** What every run shows: a dispatch on the queue, or an evaluation on copies
 *  of a labelled set's claims, with N claim agents at once on a model, what
 *  its model calls cost, and its time and summary once it ends. */
export interface RunFacts {
  run_id: number;
  kind: "dispatch" | "evaluation";
  agents: number;
  /** The version of the claim agent's configuration it used, and its model */
  version: number;
  model: string;
  reasoning_effort: string;
  evaluation_set: EvaluationSet | null;
  tiny: boolean | null;
  status: RunStatus;
  started_at: string;
  finished_at: string | null;
  seconds: number | null;
  summary: RunSummary | null;
  usage: RunUsage;
}

export interface Run extends RunFacts {
  claims: RunClaim[];
}

export interface Measures {
  decision_accuracy: number;
  accuracy: number;
  cost_of_mistakes: number;
  straight_through: number;
  model_cost_per_claim: number;
  seconds_per_claim: number;
  run_seconds: number | null;
  /** The judge's average grade from 0 (F) to 3 (A), none with none graded */
  grade: number | null;
  /** What the judge cost, apart from the claim agents */
  judge_cost: number;
}

/** An evaluation's copy, the agent's decision beside the handler's. */
export interface EvaluationClaim extends RunClaim {
  copy_of: string;
  reasons: string | null;
  handler_decision: DecisionKind;
  handler_payout: number;
  right: boolean;
  mistake_cost: number;
  /** The judge's grade, its most likely level and the probability of each
   *  check, none when it couldn't grade the copy */
  grade: number | null;
  letter: Letter | null;
  same_grounds: number | null;
  same_section: number | null;
  judge_cost: number;
}

/** The judge's levels, from F to A */
export type Letter = "F" | "C" | "B" | "A";

export interface Evaluation extends RunFacts {
  measures: Measures;
  claims: EvaluationClaim[];
}

export interface InsightTotals {
  claims: number;
  decided: number;
  straight_through: number;
  sign_offs: number;
  referred: number;
  waiting_for_handler: number;
  tool_calls: number;
  refused: number;
  median_seconds: number | null;
  longest_seconds: number | null;
  claimed: number;
  approved: number;
  paid: number;
  held: number;
}

export interface TypeMix {
  claim_type: string;
  approve: number;
  decline: number;
  refer: number;
}

export interface ToolUse {
  tool: string;
  calls: number;
  refused: number;
}

export interface SectionCount {
  section: string;
  claims: number;
}

export interface ClaimWork {
  claim_id: string;
  claim_type: string;
  status: ClaimStatus;
  decision: DecisionKind | null;
  started_at: string;
  finished_at: string;
  seconds: number;
  tool_calls: number;
  refused: number;
}

export interface Insights {
  totals: InsightTotals;
  by_type: TypeMix[];
  tools: ToolUse[];
  sections: SectionCount[];
  claims: ClaimWork[];
}
