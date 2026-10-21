import { useState } from "react";
import { api, type AgentState, type ModelChoice } from "./api";
import { useAction, useModelChoice } from "./hooks";

// A trial run's size until someone picks another
const TRIAL = 5;

function describe(agent: AgentState | null): string {
  if (agent === null) return "Checking the agent";
  if (!agent.running) return "The agent is idle";
  const where = agent.claim_id ? `on ${agent.claim_id}` : "starting up";
  const doing =
    agent.mode === "queue"
      ? `Working through the queue, ${where}`
      : `Working ${where}`;
  return agent.model ? `${doing}, with ${agent.model}` : doing;
}

/** A button's label with its number of claims, when there are any. */
function counted(label: string, claims: number): string {
  return claims >= 1 ? `${label} ${String(claims)}` : label;
}

/** How many claims Run takes: the cap, no more than are waiting, and none when
 *  the claims field is empty. */
function capped(cap: string, waiting: number): number {
  const claims = Math.min(Math.floor(Number(cap)), waiting);
  return Number.isNaN(claims) ? 0 : claims;
}

function ModelPicker({
  models,
  value,
  error,
  onChange,
}: Readonly<{
  models: ModelChoice[];
  value: string;
  error: string | null;
  onChange: (spec: string) => void;
}>) {
  return (
    <label className="field">
      <span>Model</span>
      <select
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      >
        {models.map((model) => (
          <option key={model.spec} value={model.spec}>
            {model.default ? `${model.label} (default)` : model.label}
          </option>
        ))}
      </select>
      {error && (
        <span className="agent-bar__error">
          Couldn't load the models: {error}
        </span>
      )}
    </label>
  );
}

export function AgentBar({
  agent,
  waiting,
  onChange,
}: Readonly<{
  agent: AgentState | null;
  waiting: number;
  onChange: () => void;
}>) {
  const { busy, error, run: act } = useAction(onChange);
  const { models, model, error: modelsError, pick } = useModelChoice();
  const [cap, setCap] = useState(String(TRIAL));
  const running = agent?.running ?? false;
  const claims = capped(cap, waiting);
  const cannotRunAll = busy || running || waiting === 0 || model === "";
  const cannotRun = cannotRunAll || claims < 1;

  return (
    <section
      className={`agent-bar${running ? " agent-bar--running" : ""}`}
      aria-label="UnderCover Agent"
    >
      <span className="agent-bar__pulse" aria-hidden="true" />
      <div className="agent-bar__text">
        <strong>UnderCover Agent</strong>
        <span>{describe(agent)}</span>
        {error && <span className="agent-bar__error">{error}</span>}
      </div>
      <div className="agent-bar__controls">
        <ModelPicker
          models={models}
          value={model}
          error={modelsError}
          onChange={pick}
        />
        <label className="field field--narrow">
          <span>Claims</span>
          <input
            type="number"
            min={1}
            step={1}
            value={cap}
            onChange={(event) => {
              setCap(event.target.value);
            }}
          />
        </label>
      </div>
      <div className="agent-bar__actions">
        <button
          type="button"
          className="button button--primary"
          disabled={cannotRun}
          onClick={() => {
            act(() => api.runQueue(claims, model));
          }}
        >
          {counted("Run", claims)}
        </button>
        <button
          type="button"
          className="button button--secondary"
          disabled={cannotRunAll}
          onClick={() => {
            act(() => api.runQueue(waiting, model));
          }}
        >
          {counted("Run all", waiting)}
        </button>
        <button
          type="button"
          className="button button--danger"
          disabled={busy || !running}
          onClick={() => {
            act(api.stopAgent);
          }}
        >
          Stop
        </button>
      </div>
    </section>
  );
}
