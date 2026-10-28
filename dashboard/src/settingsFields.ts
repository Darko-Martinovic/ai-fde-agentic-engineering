import type { SettingsIn } from "./api";
import { money } from "./format";

/* The platform's settings as the Settings page lists them: each with its
 * label, its unit, and how it reads. */

type Margin = "accuracy" | "grade" | "cost_per_claim" | "seconds_per_claim";

export type FieldKey =
  | "approval_limit"
  | "spending_limit"
  | "agents"
  | `objectives.${"accuracy" | "grade"}`
  | `${"noise" | "tolerance"}.${Margin}`;

export interface Field {
  key: FieldKey;
  label: string;
  unit: string;
  step: string;
  read: (value: number) => string;
}

export interface FieldGroup {
  title: string;
  purpose: string;
  fields: Field[];
}

const share = (value: number) => `${String(Math.round(value * 1000) / 10)}%`;
const grade = (value: number) => value.toFixed(2);
const whole = (value: number) => String(value);

function margins(group: "noise" | "tolerance"): Field[] {
  return [
    {
      key: `${group}.accuracy`,
      label: "Accuracy",
      unit: "a difference",
      step: "0.01",
      read: share,
    },
    {
      key: `${group}.grade`,
      label: "Grade",
      unit: "a difference",
      step: "0.01",
      read: grade,
    },
    {
      key: `${group}.cost_per_claim`,
      label: "Cost per claim",
      unit: "a fraction of the old",
      step: "0.01",
      read: share,
    },
    {
      key: `${group}.seconds_per_claim`,
      label: "Time per claim",
      unit: "a fraction of the old",
      step: "0.01",
      read: share,
    },
  ];
}

export const GROUPS: FieldGroup[] = [
  {
    title: "Approval limit",
    purpose:
      "A payout over the limit waits for a handler who can sign it off. A change applies to the decisions recorded after it.",
    fields: [
      {
        key: "approval_limit",
        label: "Approval limit",
        unit: "US dollars",
        step: "0.01",
        read: money,
      },
    ],
  },
  {
    title: "Business objectives",
    purpose:
      "The floors a new version must reach on the held-out claims to be kept.",
    fields: [
      {
        key: "objectives.accuracy",
        label: "Accuracy",
        unit: "0 to 1",
        step: "0.01",
        read: share,
      },
      {
        key: "objectives.grade",
        label: "Grade",
        unit: "0 (F) to 3 (A)",
        step: "0.01",
        read: grade,
      },
    ],
  },
  {
    title: "Noise",
    purpose: "How far a measure must improve before it counts.",
    fields: margins("noise"),
  },
  {
    title: "Tolerance",
    purpose:
      "How far a measure may get worse in a version that improves another.",
    fields: margins("tolerance"),
  },
  {
    title: "Rounds of improvement",
    purpose:
      "What a round may spend on the improver, its evaluations and the judge, and how many claim agents its evaluations use.",
    fields: [
      {
        key: "spending_limit",
        label: "Spending limit for each round",
        unit: "US dollars",
        step: "0.01",
        read: money,
      },
      {
        key: "agents",
        label: "Claim agents at once",
        unit: "1 to 25",
        step: "1",
        read: whole,
      },
    ],
  },
];

export const FIELDS: Field[] = GROUPS.flatMap((group) => group.fields);

type Single = "approval_limit" | "spending_limit" | "agents";
type Group = "objectives" | "noise" | "tolerance";

/** A field's key as the setting it names, and the measure within it. */
function parts(key: FieldKey): [Single | Group, string | undefined] {
  const [setting, measure] = key.split(".");
  return [setting as Single | Group, measure];
}

/** One setting's value. */
export function valueAt(settings: SettingsIn, key: FieldKey): number {
  const [setting, measure] = parts(key);
  if (measure === undefined) return settings[setting as Single];
  const values: Partial<Record<string, number>> = {
    ...settings[setting as Group],
  };
  return values[measure] ?? 0;
}

/** The settings with one value changed. */
export function withValue(
  settings: SettingsIn,
  key: FieldKey,
  value: number,
): SettingsIn {
  const [setting, measure] = parts(key);
  if (measure === undefined) return { ...settings, [setting]: value };
  return {
    ...settings,
    [setting]: { ...settings[setting as Group], [measure]: value },
  };
}
