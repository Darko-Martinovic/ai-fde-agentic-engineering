import type { AgentState, Insights, ModelChoice, Run } from "./api";

/* Test fixtures for the agent: its models, state, runs and insights. */

export const MODELS: ModelChoice[] = [
  {
    spec: "openrouter:deepseek/deepseek-v4.1-flash",
    label: "DeepSeek V4.1 Flash",
    default: true,
  },
  {
    spec: "anthropic:claude-haiku-5-5",
    label: "Claude Haiku 5.5",
    default: false,
  },
];

/** A queue run on Claude Haiku 5.5, five claims capped, two started: CLM-1001
 *  done and CLM-1002 being worked. */
export function run(overrides: Partial<Run> = {}): Run {
  return {
    run_id: 1,
    mode: "queue",
    cap: 5,
    model: "anthropic:claude-haiku-5-5",
    status: "running",
    started_at: "2026-10-21T10:00:00Z",
    finished_at: null,
    summary: null,
    todos: [
      { content: "Work CLM-1001", status: "completed" },
      { content: "Work CLM-1002", status: "in_progress" },
    ],
    claims_started: ["CLM-1001", "CLM-1002"],
    usage: {
      model_calls: 16,
      input_tokens: 72240,
      output_tokens: 4316,
      cost: 0.0094,
      seconds: 39,
    },
    ...overrides,
  };
}

export const IDLE: AgentState = {
  model: null,
  running: false,
  mode: null,
  claim_id: null,
};

export const NO_INSIGHTS: Insights = {
  totals: {
    claims: 25,
    decided: 0,
    straight_through: 0,
    sign_offs: 0,
    referred: 0,
    waiting_for_handler: 0,
    tool_calls: 0,
    refused: 0,
    median_seconds: null,
    longest_seconds: null,
    claimed: 0,
    approved: 0,
    paid: 0,
    held: 0,
  },
  by_type: [],
  tools: [],
  sections: [],
  claims: [],
};

export const INSIGHTS: Insights = {
  totals: {
    claims: 25,
    decided: 4,
    straight_through: 2,
    sign_offs: 1,
    referred: 1,
    waiting_for_handler: 2,
    tool_calls: 5,
    refused: 1,
    median_seconds: 7,
    longest_seconds: 10,
    claimed: 6720,
    approved: 1570,
    paid: 420,
    held: 1150,
  },
  by_type: [
    { claim_type: "baggage", approve: 1, decline: 0, refer: 0 },
    { claim_type: "emergency_medical", approve: 0, decline: 1, refer: 1 },
    { claim_type: "trip_delay", approve: 1, decline: 0, refer: 0 },
  ],
  tools: [
    { tool: "decide_claim", calls: 2, refused: 0 },
    { tool: "pay_claim", calls: 2, refused: 1 },
    { tool: "get_claim", calls: 1, refused: 0 },
  ],
  sections: [
    { section: "Section 7, Emergency Medical", claims: 2 },
    { section: "Section 3, Trip Delay", claims: 1 },
  ],
  claims: [
    {
      claim_id: "CLM-1001",
      claim_type: "trip_delay",
      status: "decided",
      decision: "approve",
      started_at: "2026-10-19T10:00:00+00:00",
      finished_at: "2026-10-19T10:00:10+00:00",
      seconds: 10,
      tool_calls: 3,
      refused: 0,
    },
    {
      claim_id: "CLM-1002",
      claim_type: "baggage",
      status: "awaiting_sign_off",
      decision: "approve",
      started_at: "2026-10-19T10:00:12+00:00",
      finished_at: "2026-10-19T10:00:16+00:00",
      seconds: 4,
      tool_calls: 2,
      refused: 1,
    },
  ],
};
