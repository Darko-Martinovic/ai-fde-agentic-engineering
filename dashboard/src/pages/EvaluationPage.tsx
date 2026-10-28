import { PageHeader } from "../components/PageHeader";
import { StateMessage } from "../components/StateMessage";
import { useCallback } from "react";
import {
  api,
  type DecisionKind,
  type Evaluation,
  type EvaluationClaim,
} from "../api";
import { DecisionBadge, Panel } from "../components/elements";
import { cost, duration, money, when } from "../format";
import { useModelLabel, usePoll } from "../hooks";
import { measureCells, modelWithEffort, whichClaims } from "../evaluations";
import { paths } from "../paths";
import { GradeChip } from "../components/GradeChip";
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
      <td>
        <GradeChip copy={copy} />
      </td>
      <td className="mono numeric">{money(copy.mistake_cost)}</td>
      <td className="mono numeric">{cost(copy.model_cost)}</td>
      <td className="mono numeric">{duration(copy.seconds)}</td>
      <td className="reasons">
        <span className="reasons__text" title={copy.reasons ?? ""}>
          {copy.reasons ?? ""}
        </span>
      </td>
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
        <dt>Version</dt>
        <dd>
          <a href={paths.version(evaluation.version)}>
            {String(evaluation.version)}
          </a>
        </dd>
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
      <div>
        <dt>Judge cost</dt>
        <dd>{cost(evaluation.measures.judge_cost)}</dd>
      </div>
    </dl>
  );
}

function EvaluationView({ evaluation }: Readonly<{ evaluation: Evaluation }>) {
  return (
    <>
      <Panel title="What it measured" className="panel--run">
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
              <th>Grade</th>
              <th className="numeric">Mistake cost</th>
              <th className="numeric">Model cost</th>
              <th className="numeric">Time</th>
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
      <PageHeader
        title={`Evaluation #${String(runId)}`}
        purpose="Each copy the claim agents worked, beside the handler's decision on the claim it copies, with the judge's grade of the agent's reasons."
        action={evaluation.data && <RunBadge status={evaluation.data.status} />}
      />
      {evaluation.error && (
        <StateMessage
          kind="error"
          message={evaluation.error}
          onRetry={evaluation.reload}
        />
      )}
      {evaluation.data === null && !evaluation.error && (
        <StateMessage
          kind="loading"
          message={`Loading evaluation #${String(runId)}`}
        />
      )}
      {evaluation.data && <EvaluationView evaluation={evaluation.data} />}
    </div>
  );
}
