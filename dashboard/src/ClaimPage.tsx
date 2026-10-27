import { useCallback } from "react";
import { api, type Claim, type Step } from "./api";
import {
  CustomerPanel,
  DocumentsPanel,
  ItemsPanel,
  PolicyPanel,
  StoryPanel,
} from "./ClaimParts";
import { ClaimType, ErrorNote, Loading, StatusBadge } from "./components";
import { DecisionPanel } from "./Decisions";
import { date, money } from "./format";
import { usePoll } from "./hooks";
import { SectionsPanel } from "./Sections";
import { StepsPanel } from "./Steps";
import { paths } from "./paths";

function ClaimHead({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <header className="claim-head">
      <div>
        <p className="claim-head__id mono">{claim.claim_id}</p>
        <h1>{claim.summary}</h1>
        <p className="claim-head__meta">
          <ClaimType type={claim.claim_type} />
          <span>{claim.incident_location}</span>
          <span>Submitted {date(claim.submitted_on)}</span>
          <span className="mono">{money(claim.amount_claimed)}</span>
        </p>
      </div>
      <div className="claim-head__side">
        <StatusBadge status={claim.status} />
      </div>
    </header>
  );
}

function ClaimView({
  claim,
  steps,
  live,
  onChange,
}: Readonly<{
  claim: Claim;
  steps: Step[] | null;
  live: boolean;
  onChange: () => void;
}>) {
  const { policy_id: policyId, customer_id: customerId } = claim;
  const policy = usePoll(
    useCallback(
      (signal: AbortSignal) => api.getPolicy(policyId, signal),
      [policyId],
    ),
    null,
  );
  const customer = usePoll(
    useCallback(
      (signal: AbortSignal) => api.getCustomer(customerId, signal),
      [customerId],
    ),
    null,
  );
  const handlers = usePoll(api.listHandlers, null);

  return (
    <>
      <ClaimHead claim={claim} />
      <div className="claim-grid">
        <div className="claim-grid__main">
          <StoryPanel claim={claim} />
          <ItemsPanel claim={claim} />
          <DocumentsPanel claim={claim} />
          <SectionsPanel steps={steps} />
          <StepsPanel steps={steps} live={live} />
        </div>
        <div className="claim-grid__side">
          <DecisionPanel
            claim={claim}
            handlers={handlers.data ?? []}
            onChange={onChange}
          />
          <PolicyPanel policy={policy.data} />
          <CustomerPanel customer={customer.data} />
        </div>
      </div>
    </>
  );
}

export function ClaimPage({ claimId }: Readonly<{ claimId: string }>) {
  const claim = usePoll(
    useCallback(
      (signal: AbortSignal) => api.getClaim(claimId, signal),
      [claimId],
    ),
    2000,
  );
  const live = claim.data?.status === "in_progress";
  const steps = usePoll(
    useCallback(
      (signal: AbortSignal) => api.listSteps(claimId, signal),
      [claimId],
    ),
    live ? 2000 : null,
  );
  const refresh = () => {
    claim.reload();
    steps.reload();
  };

  return (
    <div className="page">
      <a className="back" href={paths.queue}>
        Back to the queue
      </a>
      {claim.error && (
        <ErrorNote message={claim.error} onRetry={claim.reload} />
      )}
      {claim.data === null && !claim.error && (
        <Loading label={`Loading ${claimId}`} />
      )}
      {claim.data && (
        <ClaimView
          claim={claim.data}
          steps={steps.data}
          live={live}
          onChange={refresh}
        />
      )}
    </div>
  );
}
