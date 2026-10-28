import type {
  Evaluation,
  EvaluationClaim,
  Insights,
  Run,
  RunClaim,
} from "./api";

/* Test fixtures for the agent: its dispatches and insights. */

/** A claim in a dispatch: CLM-1001, decided and paid $420.00, by default. */
export function runClaim(overrides: Partial<RunClaim> = {}): RunClaim {
  return {
    claim_id: "CLM-1001",
    claim_type: "trip_delay",
    customer_name: "Priya Shah",
    amount_claimed: 420,
    submitted_on: "2026-09-02",
    status: "decided",
    decision: "approve",
    payout: 420,
    paid: 420,
    started_at: "2026-10-27T10:00:01Z",
    seconds: 12.4,
    model_cost: 0.0011,
    ...overrides,
  };
}

/** A dispatch on GPT-6 Luna with three claim agents, running: CLM-1001 done
 *  and CLM-1002 being worked. */
export function run(overrides: Partial<Run> = {}): Run {
  return {
    run_id: 7,
    kind: "dispatch",
    agents: 3,
    version: 1,
    model: "openai/gpt-6-luna",
    reasoning_effort: "low",
    round_id: null,
    evaluation_set: null,
    tiny: null,
    status: "running",
    started_at: "2026-10-27T10:00:00Z",
    finished_at: null,
    seconds: null,
    summary: null,
    usage: {
      model_calls: 9,
      input_tokens: 41230,
      output_tokens: 2210,
      cost: 0.0204,
    },
    claims: [
      runClaim(),
      runClaim({
        claim_id: "CLM-1002",
        customer_name: "Tom Becker",
        status: "in_progress",
        decision: null,
        payout: null,
        paid: null,
        seconds: 6,
        model_cost: 0.0004,
      }),
    ],
    ...overrides,
  };
}

/** A copy in evaluation #4, right by default: CLM-1104 approved for $250.00
 *  as the handler did. */
export function copy(
  overrides: Partial<EvaluationClaim> = {},
): EvaluationClaim {
  return {
    ...runClaim({
      claim_id: "CLM-1104-E4",
      decision: "approve",
      payout: 250,
      seconds: 40,
      model_cost: 0.0125,
    }),
    copy_of: "CLM-1104",
    reasons: "The bag was delayed 30 hours, and the receipts cover it.",
    handler_decision: "approve",
    handler_payout: 250,
    right: true,
    mistake_cost: 0,
    grade: 2.2,
    letter: "B",
    same_grounds: 0.8,
    same_section: 0.3,
    judge_cost: 0.00002,
    ...overrides,
  };
}

/** Evaluation #4 of the held-out set's five tiny claims, finished: two right,
 *  CLM-1106 over by $50.00, CLM-1110 referred, and CLM-1114 not decided. */
export function evaluation(overrides: Partial<Evaluation> = {}): Evaluation {
  return {
    ...run({ run_id: 4, kind: "evaluation", agents: 5, status: "finished" }),
    evaluation_set: "held_out",
    tiny: true,
    finished_at: "2026-10-27T10:02:41Z",
    seconds: 161,
    measures: {
      decision_accuracy: 0.8,
      accuracy: 0.4,
      cost_of_mistakes: 1600,
      straight_through: 0.6,
      model_cost_per_claim: 0.0125,
      seconds_per_claim: 40,
      run_seconds: 161,
      grade: 2.2,
      judge_cost: 0.0001,
    },
    claims: [
      copy(),
      copy({
        claim_id: "CLM-1106-E4",
        copy_of: "CLM-1106",
        payout: 300,
        right: false,
        mistake_cost: 50,
      }),
      copy({
        claim_id: "CLM-1114-E4",
        copy_of: "CLM-1114",
        decision: null,
        payout: null,
        reasons: null,
        handler_decision: "decline",
        handler_payout: 0,
        right: false,
        mistake_cost: 50,
      }),
    ],
    ...overrides,
  };
}

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
