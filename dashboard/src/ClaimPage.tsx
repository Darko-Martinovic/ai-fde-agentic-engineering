import { useCallback, useState } from "react";
import { api, type AgentState, type Claim } from "./api";
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
import { errorMessage, usePoll } from "./hooks";
import { StepsPanel } from "./Steps";

function AgentControls({
  claim,
  agent,
  onChange,
}: Readonly<{
  claim: Claim;
  agent: AgentState | null;
  onChange: () => void;
}>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const running = agent?.running ?? false;
  const workingHere = running && agent?.claim_id === claim.claim_id;
  const stranded = !running && claim.status === "in_progress";

  const act = (action: () => Promise<AgentState>) => {
    setBusy(true);
    setError(null);
    action()
      .catch((reason: unknown) => {
        setError(errorMessage(reason));
      })
      .finally(() => {
        setBusy(false);
        onChange();
      });
  };

  return (
    <div className="agent-controls">
      {claim.status === "waiting" && (
        <button
          type="button"
          className="button button--primary"
          disabled={busy || running}
          title={running ? "The agent is working on another claim" : undefined}
          onClick={() => {
            act(() => api.runClaim(claim.claim_id));
          }}
        >
          Run the agent
        </button>
      )}
      {workingHere && (
        <button
          type="button"
          className="button button--danger"
          disabled={busy}
          onClick={() => {
            act(api.stopAgent);
          }}
        >
          Stop
        </button>
      )}
      {stranded && (
        <button
          type="button"
          className="button button--secondary"
          disabled={busy}
          onClick={() => {
            act(api.stopAgent);
          }}
        >
          Return to the queue
        </button>
      )}
      {error && <span className="form-error">{error}</span>}
    </div>
  );
}

export function ClaimPage({ claimId }: Readonly<{ claimId: string }>) {
  const agent = usePoll(api.agent, 2000);
  const claim = usePoll(
    useCallback((signal: AbortSignal) => api.claim(claimId, signal), [claimId]),
    2000,
  );
  const live =
    claim.data?.status === "in_progress" ||
    (agent.data?.running === true && agent.data.claim_id === claimId);
  const steps = usePoll(
    useCallback((signal: AbortSignal) => api.steps(claimId, signal), [claimId]),
    live ? 2000 : null,
  );
  const policyId = claim.data?.policy_id;
  const customerId = claim.data?.customer_id;
  const policy = usePoll(
    useCallback(
      (signal: AbortSignal) =>
        policyId ? api.policy(policyId, signal) : Promise.resolve(null),
      [policyId],
    ),
    null,
  );
  const customer = usePoll(
    useCallback(
      (signal: AbortSignal) =>
        customerId ? api.customer(customerId, signal) : Promise.resolve(null),
      [customerId],
    ),
    null,
  );
  const handlers = usePoll(api.handlers, null);
  const refresh = () => {
    claim.reload();
    agent.reload();
    steps.reload();
  };

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
        <>
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
            <div className="claim-head__side">
              <StatusBadge status={claim.data.status} />
              <AgentControls
                claim={claim.data}
                agent={agent.data}
                onChange={refresh}
              />
            </div>
          </header>
          <div className="claim-grid">
            <div className="claim-grid__main">
              <StoryPanel claim={claim.data} />
              <ItemsPanel claim={claim.data} />
              <DocumentsPanel claim={claim.data} />
              <StepsPanel steps={steps.data} live={live} />
            </div>
            <div className="claim-grid__side">
              <DecisionPanel
                claim={claim.data}
                handlers={handlers.data ?? []}
                onChange={refresh}
              />
              <PolicyPanel policy={policy.data} />
              <CustomerPanel customer={customer.data} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
