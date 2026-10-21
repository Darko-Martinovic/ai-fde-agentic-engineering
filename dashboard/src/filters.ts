import type { ClaimStatus, ClaimSummary } from "./api";
import { humanize } from "./format";

export interface Filters {
  status: ClaimStatus | "all";
  type: string;
  search: string;
}

export type SortKey =
  | "claim_id"
  | "claim_type"
  | "customer_name"
  | "submitted_on"
  | "amount_claimed"
  | "payout"
  | "status";

export interface Sort {
  key: SortKey;
  ascending: boolean;
}

export function filterClaims(
  claims: ClaimSummary[],
  filters: Filters,
): ClaimSummary[] {
  const search = filters.search.trim().toLowerCase();
  return claims.filter(
    (c) =>
      (filters.status === "all" || c.status === filters.status) &&
      (filters.type === "all" || c.claim_type === filters.type) &&
      (search === "" ||
        [c.claim_id, c.customer_name, humanize(c.claim_type)].some((field) =>
          field.toLowerCase().includes(search),
        )),
  );
}

function compare(a: ClaimSummary, b: ClaimSummary, key: SortKey): number {
  const left = a[key] ?? -1;
  const right = b[key] ?? -1;
  if (typeof left === "number" && typeof right === "number") {
    return left - right;
  }
  return String(left).localeCompare(String(right));
}

export function sortClaims(claims: ClaimSummary[], sort: Sort): ClaimSummary[] {
  const sign = sort.ascending ? 1 : -1;
  return [...claims].sort((a, b) => sign * compare(a, b, sort.key));
}

export function countByStatus(
  claims: ClaimSummary[],
): Record<ClaimStatus, number> {
  const counts: Record<ClaimStatus, number> = {
    waiting: 0,
    in_progress: 0,
    awaiting_sign_off: 0,
    referred: 0,
    left_for_handler: 0,
    decided: 0,
  };
  for (const claim of claims) counts[claim.status] += 1;
  return counts;
}

export interface Totals {
  claimed: number;
  paid: number;
  held: number;
}

export function totals(claims: ClaimSummary[]): Totals {
  return claims.reduce<Totals>(
    (sum, c) => ({
      claimed: sum.claimed + c.amount_claimed,
      paid: sum.paid + (c.paid ?? 0),
      held: sum.held + (c.status === "awaiting_sign_off" ? (c.payout ?? 0) : 0),
    }),
    { claimed: 0, paid: 0, held: 0 },
  );
}

export function claimTypes(claims: ClaimSummary[]): string[] {
  return [...new Set(claims.map((c) => c.claim_type))].sort((a, b) =>
    a.localeCompare(b),
  );
}
