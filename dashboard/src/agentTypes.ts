import type { ClaimStatus, DecisionKind } from "./claimTypes";

/* What the agent, its runs and its work look like, as the backend sends them. */

/** The two agents: the queue agent and the claim agent it hands claims to. */
export type AgentName = "queue" | "claim";

export interface ModelChoice {
  spec: string;
  label: string;
  default: boolean;
}

export interface AgentState {
  model: string | null;
  running: boolean;
  mode: AgentName | null;
  claim_id: string | null;
}

export type RunStatus = "running" | "finished" | "stopped";

export type TodoStatus =
  "pending" | "in_progress" | "completed" | "left_for_handler";

export interface Todo {
  content: string;
  status: TodoStatus;
}

export interface RunUsage {
  model_calls: number;
  input_tokens: number;
  output_tokens: number;
  cost: number;
  seconds: number;
}

/** A run of the agent: its model, cap, to-do list, the claims it started, its
 *  usage so far and, once it has finished, its summary for the handlers. */
export interface Run {
  run_id: number;
  mode: AgentName;
  cap: number;
  model: string;
  status: RunStatus;
  started_at: string;
  finished_at: string | null;
  summary: string | null;
  todos: Todo[];
  claims_started: string[];
  usage: RunUsage;
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
