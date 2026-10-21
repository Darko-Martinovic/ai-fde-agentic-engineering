import { useCallback, useMemo } from "react";
import {
  api,
  type ClaimSummary,
  type Run,
  type Todo,
  type TodoStatus,
} from "./api";
import {
  ErrorNote,
  FIRST_STEP,
  LiveBadge,
  Markdown,
  Panel,
  StatusBadge,
} from "./components";
import { clock, cost, count, duration } from "./format";
import { useModelLabel, useNow, usePoll } from "./hooks";
import { paths } from "./paths";
import { latestAttempt, progress, type Progress } from "./runs";
import { StepList } from "./Steps";

const TODO_LABELS: Record<TodoStatus, string> = {
  pending: "To do",
  in_progress: "In progress",
  completed: "Done",
  left_for_handler: "Left for a handler",
};

function RunState({ run }: Readonly<{ run: Run }>) {
  if (run.status === "running") return <LiveBadge />;
  const when = run.finished_at ? ` at ${clock(run.finished_at)}` : "";
  const what = run.status === "stopped" ? "Stopped" : "Finished";
  return <span className="muted">{`${what}${when}`}</span>;
}

function timeLabel(done: Progress): string {
  const taken = duration(done.elapsed);
  if (done.secondsLeft === null) return taken;
  return `${taken}, about ${duration(done.secondsLeft)} left`;
}

function RunFacts({
  run,
  label,
  done,
}: Readonly<{ run: Run; label: string; done: Progress }>) {
  const { usage } = run;
  return (
    <>
      <dl className="run-facts">
        <div>
          <dt>Model</dt>
          <dd>{label}</dd>
        </div>
        <div>
          <dt>Claims</dt>
          <dd>{`${String(done.done)} of ${String(done.total)}`}</dd>
        </div>
        <div>
          <dt>Time</dt>
          <dd>{timeLabel(done)}</dd>
        </div>
        <div>
          <dt>Model calls</dt>
          <dd>{count(usage.model_calls)}</dd>
        </div>
        <div>
          <dt>Tokens in / out</dt>
          <dd>{`${count(usage.input_tokens)} / ${count(usage.output_tokens)}`}</dd>
        </div>
        <div>
          <dt>Cost</dt>
          <dd>{cost(usage.cost)}</dd>
        </div>
      </dl>
      <progress
        className="run-progress"
        aria-label="Claims worked"
        value={done.done}
        max={done.total}
      />
    </>
  );
}

function TodoList({ todos }: Readonly<{ todos: Todo[] }>) {
  return (
    <section className="run-part" aria-label="To-do list">
      <h3>To-do list</h3>
      <ol className="todos">
        {todos.map((todo, index) => (
          <li
            key={`${String(index)}-${todo.content}`}
            className={`todo todo--${todo.status}`}
          >
            <span className="todo__mark" aria-hidden="true" />
            <span className="todo__text">{todo.content}</span>
            <span className="todo__status">{TODO_LABELS[todo.status]}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

function CurrentClaim({ claimId }: Readonly<{ claimId: string }>) {
  const steps = usePoll(
    useCallback(
      (signal: AbortSignal) => api.listSteps(claimId, signal),
      [claimId],
    ),
    1500,
  );
  const attempt = latestAttempt(steps.data ?? []);
  return (
    <section className="run-part" aria-label="The claim being worked">
      <h3>
        Working on{" "}
        <a className="mono" href={paths.claim(claimId)}>
          {claimId}
        </a>
      </h3>
      {steps.error && <ErrorNote message={steps.error} />}
      {attempt.length > 0 ? (
        <StepList steps={attempt} />
      ) : (
        <p className="muted">{FIRST_STEP}</p>
      )}
    </section>
  );
}

function RunClaims({
  run,
  claims,
}: Readonly<{ run: Run; claims: ClaimSummary[] }>) {
  const started = claims.filter((c) => run.claims_started.includes(c.claim_id));
  if (started.length === 0) return null;
  return (
    <ul className="run-claims" aria-label="Claims in this run">
      {started.map((claim) => (
        <li key={claim.claim_id}>
          <a className="mono" href={paths.claim(claim.claim_id)}>
            {claim.claim_id}
          </a>
          <StatusBadge status={claim.status} />
        </li>
      ))}
    </ul>
  );
}

function RunView({
  run,
  claims,
}: Readonly<{ run: Run; claims: ClaimSummary[] }>) {
  const label = useModelLabel(run.model);
  const now = useNow(run.status === "running" ? 1000 : null);
  const statuses = useMemo(
    () => new Map(claims.map((c) => [c.claim_id, c.status])),
    [claims],
  );
  const done = progress(run, statuses, now);

  return (
    <Panel
      title={run.mode === "queue" ? "The latest run" : "The latest claim run"}
      className="panel--run"
      actions={<RunState run={run} />}
    >
      <RunFacts run={run} label={label} done={done} />
      <RunClaims run={run} claims={claims} />
      <div className="run-grid">
        {run.todos.length > 0 && <TodoList todos={run.todos} />}
        {done.current && (
          <CurrentClaim key={done.current} claimId={done.current} />
        )}
      </div>
      {run.summary && (
        <section className="run-summary" aria-label="Summary">
          <h3>Summary for the handlers</h3>
          <Markdown text={run.summary} />
        </section>
      )}
    </Panel>
  );
}

/** The latest run as it happens: its model, progress, time left, tokens and
 *  cost, the queue agent's to-do list, the claim being worked with its steps
 *  arriving live, and the summary once it has finished. */
export function RunPanel({ claims }: Readonly<{ claims: ClaimSummary[] }>) {
  const latest = usePoll(api.getLatestRun, 2000);
  if (latest.error) {
    return <ErrorNote message={latest.error} onRetry={latest.reload} />;
  }
  if (!latest.data) return null;
  return <RunView run={latest.data} claims={claims} />;
}
