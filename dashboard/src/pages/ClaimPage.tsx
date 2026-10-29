import { PageHeader } from "../components/PageHeader";
import { StateMessage } from "../components/StateMessage";
import { useCallback } from "react";
import { api, type Claim, type Step } from "../api";
import {
  CustomerPanel,
  DocumentsPanel,
  ItemsPanel,
  PolicyPanel,
  StoryPanel,
} from "../components/ClaimParts";
import { ClaimType, StatusBadge } from "../components/elements";
import { DecisionPanel } from "../components/Decisions";
import { date, money } from "../format";
import { usePoll } from "../hooks";
import { SectionsPanel } from "../components/Sections";
import { StepsPanel } from "../components/Steps";
import { paths } from "../paths";

function ClaimHead({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <div className="claim-head">
      {claim.evaluation_id !== null && (
        <p className="claim-head__copy">
          {`A copy of ${claim.copy_of ?? ""} in `}
          <a href={paths.evaluation(claim.evaluation_id)}>
            {`evaluation #${String(claim.evaluation_id)}`}
          </a>
        </p>
      )}
      <PageHeader
        title={claim.summary}
        purpose={`Claim ${claim.claim_id}: the claim, the policy and customer it rests on, and the agent's and the handlers' work on it.`}
        action={<StatusBadge status={claim.status} />}
      />
      <p className="claim-head__meta">
        <ClaimType type={claim.claim_type} />
        <span>{claim.incident_location}</span>
        <span>Submitted {date(claim.submitted_on)}</span>
        <span className="mono">{money(claim.amount_claimed)}</span>
      </p>
    </div>
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
      (signal: AbortSignal) => api.getClaimHistory(customerId, signal),
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
          {/* Last in its column, so the sections the agent reads as it works
              move nothing below them */}
          <SectionsPanel steps={steps} />
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
        <StateMessage
          kind="error"
          message={claim.error}
          onRetry={claim.reload}
        />
      )}
      {claim.data === null && !claim.error && (
        <StateMessage kind="loading" message={`Loading ${claimId}`} />
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
