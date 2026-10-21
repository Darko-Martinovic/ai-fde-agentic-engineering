import type { ClaimStatus, ClaimWork, Run, Step } from "./api";

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

export interface Progress {
  done: number;
  total: number;
  current: string | null;
  elapsed: number;
  secondsLeft: number | null;
}

// A started claim in one of these is not done: being worked, or back in the
// queue after a failed attempt (or a Stop) for this run or another to try again
const NOT_DONE: ClaimStatus[] = ["in_progress", "waiting"];

/** How many claims the run will work: its cap, or fewer when fewer were left
 *  for it, once the claims' states are known. */
function planned(run: Run, statuses: Map<string, ClaimStatus>): number {
  if (statuses.size === 0) return run.cap;
  const waiting = [...statuses].filter(
    ([id, status]) => status === "waiting" && !run.claims_started.includes(id),
  ).length;
  return Math.min(run.cap, run.claims_started.length + waiting);
}

/** How far a run has got: the claims it started that are done, out of those
 *  it will work; the claim it's on; how long it has taken; and, once a claim
 *  is done, the time left at the pace so far. */
export function progress(
  run: Run,
  statuses: Map<string, ClaimStatus>,
  now: number,
): Progress {
  const state = (id: string) => statuses.get(id) ?? "in_progress";
  const done = run.claims_started.filter(
    (id) => !NOT_DONE.includes(state(id)),
  ).length;
  const working = run.claims_started.find(
    (id) => statuses.get(id) === "in_progress",
  );
  const total = planned(run, statuses);
  const end = run.finished_at ? seconds(run.finished_at) : now / 1000;
  const elapsed = Math.max(end - seconds(run.started_at), 0);
  const live = run.status === "running";
  return {
    done,
    total,
    current: live ? (working ?? null) : null,
    elapsed,
    secondsLeft:
      live && done > 0 && total > done
        ? (elapsed / done) * (total - done)
        : null,
  };
}

/** The steps of a claim's latest attempt: a claim tried again starts afresh,
 *  so after a failure there are none until the new attempt's first step. */
export function latestAttempt(steps: Step[]): Step[] {
  const last = steps.at(-1);
  if (!last || last.kind === "failure") return [];
  return steps.filter((step) => step.thread_id === last.thread_id);
}
