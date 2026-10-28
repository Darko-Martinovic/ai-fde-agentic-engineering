import { useState } from "react";
import { api } from "../api";
import { useAction, useModelChoice } from "../hooks";
import { AgentsChoice, ModelChoiceField } from "./RunChoices";
import { FIRST_AGENTS } from "../runs";

/** Start a dispatch of the queue with N claim agents at once on a model, or
 *  stop the one running: it starts no more claims, and those working finish. */
export function DispatchForm({
  running,
  onChange,
}: Readonly<{ running: boolean; onChange: () => void }>) {
  const [agents, setAgents] = useState(FIRST_AGENTS);
  const { models, model, error: modelsError, pick } = useModelChoice();
  const { busy, error, run } = useAction(onChange);
  const [stopping, setStopping] = useState(false);
  if (stopping && !running) setStopping(false);

  return (
    <form
      className="run-form"
      aria-label="Start a dispatch"
      onSubmit={(event) => {
        event.preventDefault();
        run(() => api.startDispatch(agents, model));
      }}
    >
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
          disabled={busy || running || model === ""}
        >
          Start a dispatch
        </button>
        {running && (
          <button
            type="button"
            className="button button--danger"
            disabled={busy || stopping}
            onClick={() => {
              run(() =>
                api.stopRun().then(() => {
                  setStopping(true);
                }),
              );
            }}
          >
            Stop
          </button>
        )}
      </div>
      {stopping && (
        <p className="muted" role="status">
          Stopping: no more claims start, and those working finish.
        </p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
