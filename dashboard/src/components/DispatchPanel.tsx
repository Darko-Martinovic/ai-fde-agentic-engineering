import { StateMessage } from "./StateMessage";
import { api, type Run, type RunClaim } from "../api";
import { DecisionBadge, Panel, StatusBadge } from "./elements";
import { clock, cost, duration, money } from "../format";
import { useModelLabel, useNow, usePoll } from "../hooks";
import { paths } from "../paths";
import { claimsDone, summaryLines } from "../runs";
import { DispatchForm } from "./DispatchForm";
import { RunBadge } from "./RunBadge";

/** How long a dispatch has taken: to its finish, or so far while it runs. */
function useRunSeconds(run: Run): number {
  const now = useNow(run.status === "running" ? 1000 : null);
  if (run.seconds !== null) return run.seconds;
  return Math.max((now - new Date(run.started_at).getTime()) / 1000, 0);
}

function RunFacts({ run }: Readonly<{ run: Run }>) {
  const label = useModelLabel(run.model);
  const seconds = useRunSeconds(run);
  const { done, total } = claimsDone(run);
  return (
    <dl className="run-facts">
      <div>
        <dt>Started</dt>
        <dd>{clock(run.started_at)}</dd>
      </div>
      <div>
        <dt>Claim agents at once</dt>
        <dd>{run.agents}</dd>
      </div>
      <div>
        <dt>Version</dt>
        <dd>
          <a href={paths.version(run.version)}>{String(run.version)}</a>
        </dd>
      </div>
      <div>
        <dt>Model</dt>
        <dd>{label}</dd>
      </div>
      <div>
        <dt>Claims done</dt>
        <dd>{`${String(done)} of ${String(total)}`}</dd>
      </div>
      <div>
        <dt>Time</dt>
        <dd>{duration(seconds)}</dd>
      </div>
      <div>
        <dt>Model cost</dt>
        <dd>{cost(run.usage.cost)}</dd>
      </div>
    </dl>
  );
}

function Outcome({ claim }: Readonly<{ claim: RunClaim }>) {
  if (claim.decision === null)
    return <span className="muted">No decision</span>;
  return (
    <>
      <DecisionBadge decision={claim.decision} />{" "}
      {claim.decision === "approve" && claim.payout !== null && (
        <span className="mono">{money(claim.payout)}</span>
      )}
    </>
  );
}

function RunClaims({ claims }: Readonly<{ claims: RunClaim[] }>) {
  if (claims.length === 0) {
    return <p className="muted">No claims to work.</p>;
  }
  return (
    <div className="table-scroll">
      <table className="queue-table" aria-label="The dispatch's claims">
        <thead>
          <tr>
            <th>Claim</th>
            <th>Customer</th>
            <th>Where it stands</th>
            <th>Decision</th>
            <th className="numeric">Time</th>
            <th className="numeric">Model cost</th>
          </tr>
        </thead>
        <tbody>
          {claims.map((claim) => (
            <tr key={claim.claim_id}>
              <td>
                <a className="mono" href={paths.claim(claim.claim_id)}>
                  {claim.claim_id}
                </a>
              </td>
              <td>{claim.customer_name}</td>
              <td>
                <StatusBadge status={claim.status} />
              </td>
              <td>
                <Outcome claim={claim} />
              </td>
              <td className="mono numeric">{duration(claim.seconds)}</td>
              <td className="mono numeric">{cost(claim.model_cost)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RunView({ run }: Readonly<{ run: Run }>) {
  return (
    <Panel
      title={`Dispatch #${String(run.run_id)}`}
      className="panel--run"
      actions={<RunBadge status={run.status} />}
    >
      <RunFacts run={run} />
      <RunClaims claims={run.claims} />
      {run.summary && (
        <section className="run-summary" aria-label="Summary">
          <h3>What the dispatch left</h3>
          {summaryLines(run.summary).map((line) => (
            <p key={line}>{line}</p>
          ))}
        </section>
      )}
    </Panel>
  );
}

/** The latest dispatch as it happens: its claim agents and model, each of its
 *  claims and where it stands, its cost and time, and, once it has finished,
 *  what it left, from the records. */
export function DispatchPanel() {
  const latest = usePoll(api.getLatestDispatch, 2000);
  const running = latest.data?.status === "running";
  return (
    <>
      <DispatchForm running={running} onChange={latest.reload} />
      {latest.error && (
        <StateMessage
          kind="error"
          message={latest.error}
          onRetry={latest.reload}
        />
      )}
      {!latest.error && latest.data === null && (
        <Panel title="The latest dispatch" className="panel--run">
          <StateMessage
            kind="empty"
            message="No dispatch yet."
            next="Choose how many claim agents work at once and start one: it works the claims in progress, then the waiting ones, oldest first."
          />
        </Panel>
      )}
      {latest.data && <RunView run={latest.data} />}
    </>
  );
}
