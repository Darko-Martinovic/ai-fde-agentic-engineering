import { useCallback } from "react";
import {
  api,
  type DecisionKind,
  type Evaluation,
  type EvaluationClaim,
} from "../api";
import {
  DecisionBadge,
  ErrorNote,
  Loading,
  Panel,
} from "../components/elements";
import { cost, duration, money, when } from "../format";
import { useModelLabel, usePoll } from "../hooks";
import { measureCells, modelWithEffort, whichClaims } from "../evaluations";
import { paths } from "../paths";
import { RunBadge } from "../components/RunBadge";

function Answer({
  decision,
  payout,
}: Readonly<{ decision: DecisionKind | null; payout: number | null }>) {
  if (decision === null) return <span className="muted">No decision</span>;
  return (
    <>
      <DecisionBadge decision={decision} />{" "}
      {decision === "approve" && payout !== null && (
        <span className="mono">{money(payout)}</span>
      )}
    </>
  );
}

function Verdict({ right }: Readonly<{ right: boolean }>) {
  return right ? (
    <span className="badge badge--right">Right</span>
  ) : (
    <span className="badge badge--miss">Miss</span>
  );
}

function CopyRow({ copy }: Readonly<{ copy: EvaluationClaim }>) {
  return (
    <tr>
      <td>
        <a className="mono" href={paths.claim(copy.claim_id)}>
          {copy.claim_id}
        </a>
      </td>
      <td className="mono">{copy.copy_of}</td>
      <td>
        <Answer decision={copy.handler_decision} payout={copy.handler_payout} />
      </td>
      <td>
        <Answer decision={copy.decision} payout={copy.payout} />
      </td>
      <td>
        <Verdict right={copy.right} />
      </td>
      <td className="mono">{money(copy.mistake_cost)}</td>
      <td className="mono">{cost(copy.model_cost)}</td>
      <td className="mono">{duration(copy.seconds)}</td>
      <td className="reasons">{copy.reasons ?? ""}</td>
    </tr>
  );
}

function EvaluationFacts({ evaluation }: Readonly<{ evaluation: Evaluation }>) {
  const label = useModelLabel(evaluation.model);
  return (
    <dl className="run-facts">
      <div>
        <dt>Started</dt>
        <dd>{when(evaluation.started_at)}</dd>
      </div>
      <div>
        <dt>Claims</dt>
        <dd>{whichClaims(evaluation, evaluation.claims.length)}</dd>
      </div>
      <div>
        <dt>Claim agents at once</dt>
        <dd>{evaluation.agents}</dd>
      </div>
      <div>
        <dt>Model</dt>
        <dd>{modelWithEffort(label, evaluation.reasoning_effort)}</dd>
      </div>
      {measureCells(evaluation.measures).map((cell) => (
        <div key={cell.label}>
          <dt>{cell.label}</dt>
          <dd>{cell.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function EvaluationView({ evaluation }: Readonly<{ evaluation: Evaluation }>) {
  return (
    <>
      <Panel
        title={`Evaluation #${String(evaluation.run_id)}`}
        className="panel--run"
        actions={<RunBadge status={evaluation.status} />}
      >
        <EvaluationFacts evaluation={evaluation} />
      </Panel>
      <div className="table-scroll">
        <table className="queue-table" aria-label="The evaluation's claims">
          <thead>
            <tr>
              <th>Copy</th>
              <th>Of</th>
              <th>Handler</th>
              <th>Agent</th>
              <th>Verdict</th>
              <th>Mistake cost</th>
              <th>Model cost</th>
              <th>Time</th>
              <th>The agent's reasons</th>
            </tr>
          </thead>
          <tbody>
            {evaluation.claims.map((copy) => (
              <CopyRow key={copy.claim_id} copy={copy} />
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/** One evaluation: its details and measures, and each copy with the handler's
 *  decision beside the agent's, the misses marked. */
export function EvaluationPage({ runId }: Readonly<{ runId: number }>) {
  const evaluation = usePoll(
    useCallback(
      (signal: AbortSignal) => api.getEvaluation(runId, signal),
      [runId],
    ),
    2000,
  );
  return (
    <div className="page">
      <a className="back" href={paths.scoreboard}>
        Back to the scoreboard
      </a>
      {evaluation.error && (
        <ErrorNote message={evaluation.error} onRetry={evaluation.reload} />
      )}
      {evaluation.data === null && !evaluation.error && (
        <Loading label={`Loading evaluation #${String(runId)}`} />
      )}
      {evaluation.data && <EvaluationView evaluation={evaluation.data} />}
    </div>
  );
}
