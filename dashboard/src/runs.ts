import type { ClaimStatus, ClaimWork, Run, RunSummary } from "./api";
import { money } from "./format";

/** The most claim agents a run may have working at once, and the number a
 *  form starts with. */
export const MAX_AGENTS = Number(import.meta.env.VITE_MAX_AGENTS);
export const FIRST_AGENTS = 3;

const RUN_GAP_SECONDS = 300;

function seconds(iso: string): number {
  return new Date(iso).getTime() / 1000;
}

/** The claims of the latest run: those worked one after another, with no
 *  gap over five minutes between one claim's last step and the next's first. */
export function latestRun(claims: ClaimWork[]): ClaimWork[] {
  const ordered = claims.toSorted(
    (a, b) => seconds(a.started_at) - seconds(b.started_at),
  );
  const run: ClaimWork[] = [];
  let start = Infinity;
  for (const claim of ordered.toReversed()) {
    const gap = start - seconds(claim.finished_at);
    if (run.length > 0 && gap > RUN_GAP_SECONDS) break;
    run.unshift(claim);
    start = Math.min(start, seconds(claim.started_at));
  }
  return run;
}

export interface Layout {
  start: number;
  end: number;
  bars: { claim: ClaimWork; left: number; width: number }[];
}

/** Place each claim on a line from the run's first step (0) to its last (100). */
export function layout(run: ClaimWork[]): Layout {
  const start = Math.min(...run.map((c) => seconds(c.started_at)));
  const end = Math.max(...run.map((c) => seconds(c.finished_at)));
  const span = Math.max(end - start, 1);
  return {
    start,
    end,
    bars: run.map((claim) => ({
      claim,
      left: ((seconds(claim.started_at) - start) / span) * 100,
      width:
        ((seconds(claim.finished_at) - seconds(claim.started_at)) / span) * 100,
    })),
  };
}

// A dispatch's claim in one of these isn't done: being worked, or waiting to be
const NOT_DONE: ClaimStatus[] = ["in_progress", "waiting"];

/** How many of a dispatch's claims are done, out of all it takes. */
export function claimsDone(run: Run): { done: number; total: number } {
  const done = run.claims.filter((c) => !NOT_DONE.includes(c.status)).length;
  return { done, total: run.claims.length };
}

/** The claims named, joined for a line of the summary. */
function listed(claimIds: string[]): string {
  return claimIds.join(", ");
}

/** What a dispatch left, as lines for the handlers, leaving out empty ones. */
export function summaryLines(summary: RunSummary): string[] {
  const { approved, declined, referred } = summary;
  const lines = [
    `${String(approved)} approved, ${String(declined)} declined and ${String(referred)} referred.`,
  ];
  if (summary.waiting_for_sign_off.length > 0) {
    const held = summary.waiting_for_sign_off.map(
      (h) => `${h.claim_id} ${money(h.payout)}`,
    );
    lines.push(`Waiting for sign-off: ${listed(held)}`);
  }
  if (summary.left_for_handler.length > 0) {
    lines.push(`Left for a handler: ${listed(summary.left_for_handler)}`);
  }
  if (summary.unfinished.length > 0) {
    lines.push(`Left for the next dispatch: ${listed(summary.unfinished)}`);
  }
  return lines;
}
