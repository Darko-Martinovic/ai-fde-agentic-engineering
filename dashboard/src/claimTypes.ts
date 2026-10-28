/* What claims, policies, customers and the agent's steps look like, as the
   backend sends them. */

export type ClaimStatus =
  | "waiting"
  | "in_progress"
  | "awaiting_sign_off"
  | "referred"
  | "left_for_handler"
  | "decided";

/** The states a handler decides a claim from. */
export const FOR_A_HANDLER: ClaimStatus[] = ["referred", "left_for_handler"];

export type DecisionKind = "approve" | "decline" | "refer";
export type Review = "signed_off" | "rejected";

export interface ClaimSummary {
  claim_id: string;
  claim_type: string;
  customer_name: string;
  amount_claimed: number;
  submitted_on: string;
  status: ClaimStatus;
  decision: DecisionKind | null;
  payout: number | null;
  paid: number | null;
}

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Decision {
  decided_by: string;
  decision: DecisionKind;
  payout: number;
  reasons: string;
  policy_section: string | null;
  decided_at: string;
  review: Review | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
}

export interface Payment {
  amount: number;
  authorized_by: string;
  paid_at: string;
  signed_off_at: string | null;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  items: Item[];
  amount_claimed: number;
  documents: ClaimDocument[];
  status: ClaimStatus;
  decisions: Decision[];
  payment: Payment | null;
  /** For an evaluation's copy: the evaluation, and the claim it copies. */
  evaluation_id: number | null;
  copy_of: string | null;
}

export interface Plan {
  plan: string;
  name: string;
  trip_cancellation_max: number;
  trip_delay_waiting_hours: number;
  trip_delay_max: number;
  baggage_delay_waiting_hours: number;
  baggage_delay_max: number;
  baggage_max: number;
  per_item_limit: number;
  passport_max: number;
  emergency_medical_max: number;
  deductible: number;
}

export interface AddOn {
  add_on: string;
  name: string;
  effect: string;
  electronics_per_item_limit: number | null;
}

export interface Policy {
  policy_id: string;
  customer_id: string;
  plan: Plan;
  deductible_applies_to: string[];
  add_ons: AddOn[];
  purchased_on: string;
  sold_through: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  status: string;
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  incident_date: string;
  claim_type: string;
  summary: string;
  outcome: string;
  amount_paid: number;
}

export interface Customer {
  customer_id: string;
  name: string;
  email: string;
  phone: string;
  customer_since: string;
  previous_claims: PreviousClaim[];
}

/** A handler as the decisions they sign name them. */
export interface HandlerName {
  handler_id: string;
  name: string;
  role: string;
}

export interface Handler extends HandlerName {
  email: string;
  /** Whether they can sign off payouts over the approval limit: the senior
   *  handler's actions, such as reviewing a held payout. */
  can_approve_over_limit: boolean;
}

export type StepKind =
  "tool_call" | "tool_result" | "reply" | "section" | "failure";

export type DocumentName = "wording" | "manual";

export interface SectionTitle {
  document: DocumentName;
  document_title: string;
  number: number;
  title: string;
}

export interface Section extends SectionTitle {
  text: string;
}

export interface Step {
  thread_id: string;
  kind: StepKind;
  text: string;
  recorded_at: string;
}

/** The section a `section` step names; the backend checks its shape. */
export function sectionOf(step: Step): SectionTitle {
  return JSON.parse(step.text) as SectionTitle;
}
