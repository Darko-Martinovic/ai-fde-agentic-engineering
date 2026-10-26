import { useCallback } from "react";
import { api, type AgentState, type Claim, type Step } from "./api";
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
import { useAction, useModelChoice, usePoll } from "./hooks";
import { SectionsPanel } from "./Sections";
import { StepsPanel } from "./Steps";
import { paths } from "./paths";

type AgentAction = "run" | "stop" | null;

/** What the agent can do on this claim now: run on it, or stop working on it. A
 *  claim a stopped run left in progress keeps its saved progress for the next
 *  run to carry on. */
function agentAction(claim: Claim, agent: AgentState | null): AgentAction {
  const running = agent?.running ?? false;
  if (claim.status === "waiting") return "run";
  if (running && agent?.claim_id === claim.claim_id) return "stop";
  return null;
}

function AgentControls({
  claim,
  agent,
  onChange,
}: Readonly<{
  claim: Claim;
  agent: AgentState | null;
  onChange: () => void;
}>) {
  const { busy, error, run } = useAction(onChange);
  const { model } = useModelChoice();
  const running = agent?.running ?? false;
  const action = agentAction(claim, agent);

  return (
    <div className="agent-controls">
      {action === "run" && (
        <button
          type="button"
          className="button button--primary"
          disabled={busy || running || model === ""}
          title={running ? "The agent is working on another claim" : undefined}
          onClick={() => {
            run(() => api.runClaim(claim.claim_id, model));
          }}
        >
          Run the agent
        </button>
      )}
      {action === "stop" && (
        <button
          type="button"
          className="button button--danger"
          disabled={busy}
          onClick={() => {
            run(api.stopAgent);
          }}
        >
          Stop
        </button>
      )}
      {error && <span className="form-error">{error}</span>}
    </div>
  );
}

function ClaimHead({
  claim,
  agent,
  onChange,
}: Readonly<{
  claim: Claim;
  agent: AgentState | null;
  onChange: () => void;
}>) {
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
        <AgentControls claim={claim} agent={agent} onChange={onChange} />
      </div>
    </header>
  );
}

function ClaimView({
  claim,
  agent,
  steps,
  live,
  onChange,
}: Readonly<{
  claim: Claim;
  agent: AgentState | null;
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
      <ClaimHead claim={claim} agent={agent} onChange={onChange} />
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
  const agent = usePoll(api.getAgent, 2000);
  const claim = usePoll(
    useCallback(
      (signal: AbortSignal) => api.getClaim(claimId, signal),
      [claimId],
    ),
    2000,
  );
  const live =
    claim.data?.status === "in_progress" ||
    (agent.data?.running === true && agent.data.claim_id === claimId);
  const steps = usePoll(
    useCallback(
      (signal: AbortSignal) => api.listSteps(claimId, signal),
      [claimId],
    ),
    live ? 2000 : null,
  );
  const refresh = () => {
    claim.reload();
    agent.reload();
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
          agent={agent.data}
          steps={steps.data}
          live={live}
          onChange={refresh}
        />
      )}
    </div>
  );
}
