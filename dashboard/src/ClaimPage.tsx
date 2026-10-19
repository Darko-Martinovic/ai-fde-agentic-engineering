import { useCallback } from "react";
import { api } from "./api";
import { ClaimType, ErrorNote, Loading, StatusBadge } from "./components";
import { date, money } from "./format";
import { usePoll } from "./hooks";

export function ClaimPage({ claimId }: Readonly<{ claimId: string }>) {
  const claim = usePoll(
    useCallback((signal: AbortSignal) => api.claim(claimId, signal), [claimId]),
    3000,
  );

  return (
    <div className="page">
      <a className="back" href="#/">
        Back to the queue
      </a>
      {claim.error && (
        <ErrorNote message={claim.error} onRetry={claim.reload} />
      )}
      {claim.data === null && !claim.error && (
        <Loading label={`Loading ${claimId}`} />
      )}
      {claim.data && (
        <header className="claim-head">
          <div>
            <p className="claim-head__id mono">{claim.data.claim_id}</p>
            <h1>{claim.data.summary}</h1>
            <p className="claim-head__meta">
              <ClaimType type={claim.data.claim_type} />
              <span>{claim.data.incident_location}</span>
              <span>Submitted {date(claim.data.submitted_on)}</span>
              <span className="mono">{money(claim.data.amount_claimed)}</span>
            </p>
          </div>
          <StatusBadge status={claim.data.status} />
        </header>
      )}
    </div>
  );
}
