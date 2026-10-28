import type {
  Configuration,
  SettingsView,
  Version,
  VersionDetails,
} from "./api";

/* Test fixtures for improving the claim agent: its configuration's versions
 * and the models it may use. */

/** Version 1, the claims team's, on GPT-6 Luna at low, current. */
export function version(overrides: Partial<Version> = {}): Version {
  return {
    number: 1,
    model: "openai/gpt-6-luna",
    reasoning_effort: "low",
    based_on: null,
    reason: "The claim agent as it was before versions.",
    proposed_by: "The claims team",
    approved_by: null,
    approved_at: null,
    created_at: "2026-10-28T08:00:00Z",
    verdict: "kept",
    verdict_reason: "The first version.",
    status: "current",
    lines_added: 0,
    lines_removed: 0,
    ...overrides,
  };
}

/** Version 2, under test: one rule added on Gemini, proposed by round 1 and
 *  approved by Dana Whitfield. */
export function versionDetails(
  overrides: Partial<VersionDetails> = {},
): VersionDetails {
  return {
    ...version({
      number: 2,
      model: "google/gemini-3.5-flash-lite",
      reasoning_effort: "minimal",
      based_on: 1,
      reason: "Refer claims the manual flags for review.",
      proposed_by: "Round 1",
      approved_by: "HND-01",
      approved_at: "2026-10-28T09:00:00Z",
      verdict: null,
      verdict_reason: null,
      status: "under_test",
      lines_added: 1,
      lines_removed: 1,
    }),
    instructions: "# UnderCover claim agent\n\nRefer what the manual flags.",
    based_on_model: "openai/gpt-6-luna",
    based_on_reasoning_effort: "low",
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
    ...overrides,
  };
}

export const CONFIGURATION: Configuration = {
  current: 1,
  versions: [
    version({
      number: 2,
      model: "google/gemini-3.5-flash-lite",
      reasoning_effort: "minimal",
      based_on: 1,
      proposed_by: "Round 1",
      approved_by: "HND-01",
      approved_at: "2026-10-28T09:00:00Z",
      verdict: null,
      verdict_reason: null,
      status: "under_test",
      lines_added: 1,
      lines_removed: 1,
    }),
    version(),
  ],
  models_allowed: [
    {
      model: "openai/gpt-6-luna",
      label: "GPT-6 Luna",
      provider: "openrouter",
      reasoning_efforts: ["none", "low", "medium"],
      input_price: 0.1,
      output_price: 0.5,
    },
    {
      model: "google/gemini-3.5-flash-lite",
      label: "Gemini 3.5 Flash Lite",
      provider: "openrouter",
      reasoning_efforts: ["minimal", "low"],
      input_price: 0.3,
      output_price: 2.5,
    },
  ],
};

/** The settings as Dana Whitfield last changed them, and the models allowed. */
export const SETTINGS_VIEW: SettingsView = {
  settings: {
    number: 2,
    approval_limit: 1000,
    objectives: { accuracy: 0.6, grade: 1 },
    noise: {
      accuracy: 0.1,
      grade: 0.15,
      cost_per_claim: 0.15,
      seconds_per_claim: 0.15,
    },
    tolerance: {
      accuracy: 0.1,
      grade: 0.15,
      cost_per_claim: 1,
      seconds_per_claim: 0.25,
    },
    spending_limit: 0.5,
    agents: 25,
    changed_by: "HND-01",
    changed_at: "2026-10-28T09:30:00Z",
  },
  models_allowed: CONFIGURATION.models_allowed,
};
