import type { ClaimStatus, ClaimSummary, DecisionKind } from "./claimTypes";

/* What the agent's runs and its work look like, as the backend sends them. */

export interface ModelChoice {
  spec: string;
  label: string;
  default: boolean;
}

export type RunStatus = "running" | "finished" | "stopped";

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

/** A dispatch: N claim agents at once on the queue, on a model, with its
 *  claims, what its model calls cost, and its time and summary once it ends. */
export interface Run {
  run_id: number;
  kind: "dispatch";
  agents: number;
  model: string;
  reasoning_effort: string;
  status: RunStatus;
  started_at: string;
  finished_at: string | null;
  seconds: number | null;
  summary: RunSummary | null;
  usage: RunUsage;
  claims: RunClaim[];
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
