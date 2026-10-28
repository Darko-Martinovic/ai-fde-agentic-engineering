/** The shapes of the claim agent's configuration as the backend gives them:
 *  its versions and the models it may use. */

export type VersionStatus = "current" | "kept" | "under_test" | "rolled_back";
export type Verdict = "kept" | "rolled_back";

export interface ModelAllowed {
  model: string;
  label: string;
  provider: string;
  reasoning_efforts: string[];
  /** US dollars per million tokens */
  input_price: number;
  output_price: number;
}

export interface Version {
  number: number;
  model: string;
  reasoning_effort: string;
  based_on: number | null;
  reason: string;
  proposed_by: string;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  verdict: Verdict | null;
  verdict_reason: string | null;
  status: VersionStatus;
  lines_added: number;
  lines_removed: number;
}

export interface DiffLine {
  kind: "added" | "removed" | "context";
  text: string;
}

export interface Hunk {
  heading: string;
  lines: DiffLine[];
}

export interface VersionDetails extends Version {
  instructions: string;
  based_on_model: string | null;
  based_on_reasoning_effort: string | null;
  changes: Hunk[];
}

export interface Configuration {
  current: number;
  versions: Version[];
  models_allowed: ModelAllowed[];
}

/** The floors a new version must reach on the held-out set. */
export interface Objectives {
  accuracy: number;
  grade: number;
}

/** How far each measure must move to count, or may move the wrong way. */
export interface Margins {
  accuracy: number;
  grade: number;
  cost_per_claim: number;
  seconds_per_claim: number;
}

export interface SettingsIn {
  approval_limit: number;
  objectives: Objectives;
  noise: Margins;
  tolerance: Margins;
  spending_limit: number;
  agents: number;
}

export interface PlatformSettings extends SettingsIn {
  number: number;
  changed_by: string | null;
  changed_at: string;
}

export interface SettingsView {
  settings: PlatformSettings;
  models_allowed: ModelAllowed[];
}
