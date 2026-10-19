import type { ClaimWork } from "./api";

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
