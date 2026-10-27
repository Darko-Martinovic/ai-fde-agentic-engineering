import { useState } from "react";
import { api, type Evaluation, type EvaluationSet } from "./api";
import { ErrorNote, Loading, Panel } from "./components";
import { when } from "./format";
import { useAction, useModelChoice, useModelLabels, usePoll } from "./hooks";
import {
  measureCells,
  modelWithEffort,
  SET_LABELS,
  whichClaims,
} from "./evaluations";
import { paths } from "./paths";
import { AgentsChoice, ModelChoiceField } from "./RunChoices";
import { RunBadge } from "./RunBadge";
import { FIRST_AGENTS } from "./runs";

const SETS = Object.keys(SET_LABELS) as EvaluationSet[];

/** Start an evaluation of a labelled set, whole or its five tiny claims, with
 *  N claim agents at once on a model. */
function EvaluationForm({ onChange }: Readonly<{ onChange: () => void }>) {
  const [evaluationSet, setEvaluationSet] =
    useState<EvaluationSet>("evaluation");
  const [tiny, setTiny] = useState(false);
  const [agents, setAgents] = useState(FIRST_AGENTS);
  const { models, model, error: modelsError, pick } = useModelChoice();
  const { busy, error, run } = useAction(onChange);

  return (
    <form
      className="run-form"
      aria-label="Start an evaluation"
      onSubmit={(event) => {
        event.preventDefault();
        run(() =>
          api.startEvaluation({
            evaluation_set: evaluationSet,
            tiny,
            agents,
            model,
          }),
        );
      }}
    >
      <label className="field">
        <span>Set</span>
        <select
          value={evaluationSet}
          onChange={(event) => {
            setEvaluationSet(event.target.value as EvaluationSet);
          }}
        >
          {SETS.map((set) => (
            <option key={set} value={set}>
              {SET_LABELS[set]}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        <span>Claims</span>
        <select
          value={tiny ? "tiny" : "all"}
          onChange={(event) => {
            setTiny(event.target.value === "tiny");
          }}
        >
          <option value="all">All 25</option>
          <option value="tiny">The five tiny claims</option>
        </select>
      </label>
      <AgentsChoice value={agents} onChange={setAgents} />
      <ModelChoiceField
        models={models}
        value={model}
        error={modelsError}
        onChange={pick}
      />
      <div className="run-form__actions">
        <button
          type="submit"
          className="button button--primary"
          disabled={busy || model === ""}
        >
          Start an evaluation
        </button>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}

function EvaluationRow({
  evaluation,
  label,
}: Readonly<{ evaluation: Evaluation; label: string }>) {
  return (
    <tr>
      <td>
        <a className="mono" href={paths.evaluation(evaluation.run_id)}>
          {`#${String(evaluation.run_id)}`}
        </a>
      </td>
      <td>{whichClaims(evaluation, evaluation.claims.length)}</td>
      {measureCells(evaluation.measures).map((cell) => (
        <td key={cell.label} className="mono">
          {cell.value}
        </td>
      ))}
      <td className="mono">{evaluation.agents}</td>
      <td>{modelWithEffort(label, evaluation.reasoning_effort)}</td>
      <td>
        <RunBadge status={evaluation.status} />
      </td>
      <td>{when(evaluation.started_at)}</td>
    </tr>
  );
}

function Evaluations({ evaluations }: Readonly<{ evaluations: Evaluation[] }>) {
  const labelOf = useModelLabels();
  if (evaluations.length === 0) {
    return <p className="muted">No evaluation yet.</p>;
  }
  const labels = measureCells(evaluations[0].measures).map((c) => c.label);
  return (
    <div className="table-scroll">
      <table className="queue-table scoreboard" aria-label="Evaluations">
        <thead>
          <tr>
            <th>Evaluation</th>
            <th>Claims</th>
            {labels.map((label) => (
              <th key={label}>{label}</th>
            ))}
            <th>Agents</th>
            <th>Model</th>
            <th>Status</th>
            <th>Started</th>
          </tr>
        </thead>
        <tbody>
          {evaluations.map((evaluation) => (
            <EvaluationRow
              key={evaluation.run_id}
              evaluation={evaluation}
              label={labelOf(evaluation.model)}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The scoreboard: start an evaluation, and every evaluation, newest first,
 *  with the lab's measures. */
export function ScoreboardPage() {
  const evaluations = usePoll(api.listEvaluations, 2000);
  return (
    <div className="page">
      <EvaluationForm onChange={evaluations.reload} />
      <Panel title="Scoreboard" className="panel--scoreboard">
        {evaluations.error && (
          <ErrorNote message={evaluations.error} onRetry={evaluations.reload} />
        )}
        {evaluations.data === null && !evaluations.error && (
          <Loading label="Loading the evaluations" />
        )}
        {evaluations.data && <Evaluations evaluations={evaluations.data} />}
      </Panel>
    </div>
  );
}
