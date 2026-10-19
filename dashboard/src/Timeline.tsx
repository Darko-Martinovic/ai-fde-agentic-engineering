import type { ClaimWork } from "./api";
import { DECISION_LABELS, clock, duration } from "./format";
import { latestRun, layout } from "./runs";

function at(epochSeconds: number): string {
  return clock(new Date(epochSeconds * 1000).toISOString());
}

function outcome(claim: ClaimWork): string {
  const decision = claim.decision
    ? DECISION_LABELS[claim.decision]
    : "No decision";
  return `${decision} in ${duration(claim.seconds)}`;
}

export function Timeline({ claims }: Readonly<{ claims: ClaimWork[] }>) {
  const run = latestRun(claims);
  if (run.length === 0) return null;
  const { start, end, bars } = layout(run);

  return (
    <div className="timeline">
      <p className="timeline__summary">
        {run.length} {run.length === 1 ? "claim" : "claims"} in{" "}
        {duration(end - start)}, from {at(start)} to {at(end)}
      </p>
      <ol className="timeline__rows" aria-label="The latest run">
        {bars.map(({ claim, left, width }) => (
          <li key={claim.claim_id}>
            <a className="mono" href={`#/claims/${claim.claim_id}`}>
              {claim.claim_id}
            </a>
            <span className="timeline__track">
              <span
                className={`timeline__bar tone--${claim.decision ?? "none"}`}
                style={{ left: `${String(left)}%`, width: `${String(width)}%` }}
                title={`${claim.claim_id}: ${outcome(claim)}`}
                aria-label={outcome(claim)}
              />
            </span>
            <span className="bars__note">{duration(claim.seconds)}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
